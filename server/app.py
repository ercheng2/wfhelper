#!/usr/bin/env python3
"""微信好友助手 v2.0 - 本地服务器版（纯标准库，无需安装依赖）"""

import os, sys, json, sqlite3, uuid, webbrowser, threading, socket, mimetypes, urllib.parse, urllib.request, urllib.error, base64, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# === 百度OCR配置 ===
BD_OCR_API_KEY = 'vT5a9ltdAlrz7cFMahXRfIPn'
BD_OCR_SECRET_KEY = '12Wsb2BNfRRTUG5wiDMfZXKhJWeqGcHG'
_bd_access_token = None
_bd_token_expires = 0

_bd_token_error = ''  # 保存最近一次token获取失败的详细错误

def get_bd_access_token():
    """获取百度OCR access_token，自动缓存刷新"""
    global _bd_access_token, _bd_token_expires, _bd_token_error
    import time
    if _bd_access_token and time.time() < _bd_token_expires - 60:
        return _bd_access_token
    _bd_token_error = ''
    try:
        url = f'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BD_OCR_API_KEY}&client_secret={BD_OCR_SECRET_KEY}'
        req = urllib.request.Request(url, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if 'error' in data:
            _bd_token_error = f"百度返回错误: {data.get('error_description', data.get('error', '未知'))}"
            print(f'[OCR] {_bd_token_error}')
            return None
        _bd_access_token = data.get('access_token', '')
        _bd_token_expires = time.time() + data.get('expires_in', 2592000)
        if not _bd_access_token:
            _bd_token_error = '百度返回了空token'
            return None
        return _bd_access_token
    except urllib.error.URLError as e:
        _bd_token_error = f'网络无法连接百度AI(URLError): {e.reason}'
        print(f'[OCR] {_bd_token_error}')
        return None
    except Exception as e:
        _bd_token_error = f'获取token异常({type(e).__name__}): {e}'
        print(f'[OCR] {_bd_token_error}')
        return None

def compress_image_for_ocr(file_bytes, max_size=2*1024*1024):
    """压缩图片使其适合OCR API大小限制（百度base64编码前约1.5MB）"""
    if len(file_bytes) <= max_size:
        return file_bytes
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        quality = 85
        while quality >= 30:
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=quality)
            if buf.tell() <= max_size:
                return buf.getvalue()
            quality -= 10
        scale = 0.8
        while scale >= 0.2:
            w, h = img.size
            resized = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format='JPEG', quality=75)
            if buf.tell() <= max_size:
                return buf.getvalue()
            scale -= 0.1
        return file_bytes
    except ImportError:
        return file_bytes

def ocr_recognize(file_bytes, is_pdf=False):
    """调用百度通用文字识别（高精度版），返回识别文本。支持图片和PDF格式"""
    token = get_bd_access_token()
    if not token:
        return None, 'OCR服务未授权'
    try:
        url = f'https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token={token}'
        if is_pdf:
            file_b64 = base64.b64encode(file_bytes).decode('utf-8')
            # PDF方案1：直接用百度PDF OCR（文件<7MB时，base64编码后约<10MB）
            if len(file_bytes) < 7 * 1024 * 1024:
                try:
                    all_words = []
                    for page_num in range(1, 6):
                        post_data = urllib.parse.urlencode({
                            'pdf_file': file_b64,
                            'pdf_file_num': str(page_num)
                        }).encode('utf-8')
                        req = urllib.request.Request(url, data=post_data, method='POST')
                        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            result = json.loads(resp.read().decode('utf-8'))
                        if 'error_code' in result:
                            print(f'[OCR] PDF方案1第{page_num}页失败: {result.get("error_msg","")}')
                            break
                        words = [item['words'] for item in result.get('words_result', [])]
                        if not words:
                            break
                        all_words.extend(words)
                    if all_words:
                        return all_words, None
                except Exception as e:
                    print(f'[OCR] PDF方案1异常: {e}')
            # PDF方案2：PyMuPDF转图片再OCR（纯Python，不需要poppler）
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype='pdf')
                all_words = []
                total_pages = len(doc)
                # 统一用300 DPI，确保OCR识别精度
                dpi = 300
                for page_num in range(min(total_pages, 5)):
                    page = doc[page_num]
                    pix = page.get_pixmap(dpi=dpi)
                    img_bytes = pix.tobytes('jpeg')
                    # 压缩到2MB以下（百度API base64编码后上限8MB，原文件2MB×1.37≈2.74MB足够）
                    compressed = compress_image_for_ocr(img_bytes, max_size=2*1024*1024)
                    words, err = ocr_recognize(compressed, is_pdf=False)
                    if err:
                        print(f'[OCR] PyMuPDF第{page_num+1}页OCR失败: {err}')
                        continue
                    all_words.extend(words)
                doc.close()
                if all_words:
                    return all_words, None
                return None, 'PDF转图片后OCR未识别到文字'
            except Exception as e:
                print(f'[OCR] PyMuPDF失败: {e}')
            # PDF方案3：pdf2image转图片（需要poppler）
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(file_bytes, first_page=1, last_page=5, dpi=300)
                all_words = []
                for img in images:
                    import io as _io
                    buf = _io.BytesIO()
                    img.save(buf, format='JPEG', quality=85)
                    img_bytes = buf.getvalue()
                    compressed = compress_image_for_ocr(img_bytes)
                    words, err = ocr_recognize(compressed, is_pdf=False)
                    if err:
                        continue
                    all_words.extend(words)
                if all_words:
                    return all_words, None
                return None, 'PDF转图片后OCR未识别到文字'
            except Exception as e:
                print(f'[OCR] pdf2image失败: {e}')
            return None, 'PDF识别失败（需安装pymupdf: pip install pymupdf）'
        else:
            # 图片：先压缩再OCR
            compressed = compress_image_for_ocr(file_bytes)
            file_b64 = base64.b64encode(compressed).decode('utf-8')
            data = urllib.parse.urlencode({'image': file_b64}).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            if 'error_code' in result:
                # oversize时降级到标准版（限制更宽松）
                if result.get('error_code') == 18 or 'oversize' in result.get('error_msg', '').lower():
                    url_std = f'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={token}'
                    req2 = urllib.request.Request(url_std, data=data, method='POST')
                    req2.add_header('Content-Type', 'application/x-www-form-urlencoded')
                    with urllib.request.urlopen(req2, timeout=30) as resp2:
                        result2 = json.loads(resp2.read().decode('utf-8'))
                    if 'error_code' in result2:
                        return None, f"OCR错误: {result2.get('error_msg', '未知错误')}"
                    words = [item['words'] for item in result2.get('words_result', [])]
                    return words, None
                return None, f"OCR错误: {result.get('error_msg', '未知错误')}"
            words = [item['words'] for item in result.get('words_result', [])]
            return words, None
    except Exception as e:
        return None, f'OCR请求失败: {e}'

def parse_contract_info(text_lines):
    """从OCR识别文本中提取合同关键字段 - V3: 基于真实合同OCR输出优化"""
    full_text = '\n'.join(text_lines)
    info = {}
    
    def extract_date(text):
        """从文本提取日期，支持年月日、年月（无日默认1号）"""
        patterns = [
            r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?',
            r'(\d{4})\s*[-/\.]\s*(\d{1,2})\s*[-/\.]\s*(\d{1,2})',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                try:
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if 2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                        return f'{y}-{mo:02d}-{d:02d}'
                except:
                    pass
        # 年月无日格式（如"2025年9月"）
        m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月(?!\s*\d)', text)
        if m:
            try:
                y, mo = int(m.group(1)), int(m.group(2))
                if 2000 <= y <= 2100 and 1 <= mo <= 12:
                    return f'{y}-{mo:02d}-01'
            except:
                pass
        return None
    
    def extract_all_dates(text):
        """提取文本中所有日期"""
        results = []
        patterns = [
            r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?',
            r'(\d{4})\s*[-/\.]\s*(\d{1,2})\s*[-/\.]\s*(\d{1,2})',
        ]
        for p in patterns:
            for m in re.finditer(p, text):
                try:
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if 2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                        results.append(f'{y}-{mo:02d}-{d:02d}')
                except:
                    pass
        # 年月无日格式
        for m in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月(?!\s*\d)', text):
            try:
                y, mo = int(m.group(1)), int(m.group(2))
                if 2000 <= y <= 2100 and 1 <= mo <= 12:
                    results.append(f'{y}-{mo:02d}-01')
            except:
                pass
        return results
    
    def extract_amount(text):
        """从文本提取金额"""
        m = re.search(r'[¥￥]\s*(\d[\d,，]*\.?\d*)', text)
        if m:
            s = m.group(1).replace(',', '').replace('，', '')
            try:
                val = float(s)
                if '万' in text:
                    val *= 10000
                return val
            except:
                pass
        m = re.search(r'人民币\s*(\d[\d,，]*\.?\d*)\s*(万元|元)', text)
        if m:
            s = m.group(1).replace(',', '').replace('，', '')
            try:
                val = float(s)
                if '万' in m.group(2):
                    val *= 10000
                return val
            except:
                pass
        m = re.search(r'(\d[\d,，]*\.?\d*)\s*(万元|元整|元)', text)
        if m:
            s = m.group(1).replace(',', '').replace('，', '')
            try:
                val = float(s)
                if '万' in m.group(2):
                    val *= 10000
                return val
            except:
                pass
        m = re.search(r'(\d[\d,，]*\.?\d*)\s*万(?!元)', text)
        if m:
            s = m.group(1).replace(',', '').replace('，', '')
            try:
                return float(s) * 10000
            except:
                pass
        return None
    
    def extract_company(text):
        """从文本提取公司名称"""
        m = re.search(r'([\u4e00-\u9fa5]{2,20}(?:有限责?任?公司|股份有限?公司|集团公司|公司|研究院|研究所|中心|事务所))', text)
        if m:
            return m.group(1).strip()
        m = re.search(r'[：:]\s*([\u4e00-\u9fa5]{2,30})', text)
        if m:
            return m.group(1).strip()
        return None
    
    def join_next_lines(start_idx, max_lines=3):
        """从start_idx开始，拼接后续多行形成一个完整字符串（公司名常跨行）"""
        parts = []
        for j in range(start_idx, min(start_idx + max_lines, len(text_lines))):
            parts.append(text_lines[j].strip())
        return ''.join(parts)
    
    # =====================================================
    # 第一遍：提取同行双日期"自X起至Y止"
    # =====================================================
    for line in text_lines:
        m = re.search(r'自\s*(\d{4})\s*[-年/\.]\s*(\d{1,2})\s*[-月/\.]\s*(\d{1,2})\s*日?\s*起\s*[，,]?\s*至\s*(\d{4})\s*[-年/\.]\s*(\d{1,2})\s*[-月/\.]\s*(\d{1,2})\s*日?\s*(?:止|期|$)', line)
        if m:
            try:
                sy, smo, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
                ey, emo, ed = int(m.group(4)), int(m.group(5)), int(m.group(6))
                if 2000 <= sy <= 2100 and 2000 <= ey <= 2100:
                    info['startDate'] = f'{sy}-{smo:02d}-{sd:02d}'
                    info['endDate'] = f'{ey}-{emo:02d}-{ed:02d}'
            except:
                pass
        if 'startDate' not in info:
            m = re.search(r'(?:从|自)?\s*(\d{4})\s*[-年/\.]\s*(\d{1,2})\s*[-月/\.]\s*(\d{1,2})\s*日?\s*[至到~\-—]\s*(\d{4})\s*[-年/\.]\s*(\d{1,2})\s*[-月/\.]\s*(\d{1,2})\s*日?', line)
            if m:
                try:
                    sy, smo, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    ey, emo, ed = int(m.group(4)), int(m.group(5)), int(m.group(6))
                    if 2000 <= sy <= 2100 and 2000 <= ey <= 2100:
                        info['startDate'] = f'{sy}-{smo:02d}-{sd:02d}'
                        info['endDate'] = f'{ey}-{emo:02d}-{ed:02d}'
                except:
                    pass
    
    # =====================================================
    # 合同名称
    # =====================================================
    # 1) 明确关键词 + 冒号
    name_keys = ['合同名称', '协议名称', '项目名称', '工程名称']
    for line in text_lines:
        for nk in name_keys:
            m = re.search(rf'{re.escape(nk)}\s*[：:]\s*(.+)', line)
            if m:
                val = m.group(1).strip()
                if len(val) > 2 and len(val) < 60:
                    info['name'] = val
                    break
        if 'name' in info:
            break
    # 2) 以"合同"/"协议"结尾的短行（如"销售合同"）
    if 'name' not in info:
        for line in text_lines:
            line_s = line.strip()
            if 2 <= len(line_s) <= 40 and re.search(r'(?:合同|协议|订单)$', line_s):
                if not any(k in line_s for k in ['甲方', '乙方', '签订', '金额', '日期', '条款', '第', '付款', '质保', '保修', '价格', '总价']):
                    info['name'] = line_s
                    break
    # 3) 含"项目"/"工程"关键词的短行
    if 'name' not in info:
        for line in text_lines:
            line_s = line.strip()
            if 4 <= len(line_s) <= 40 and re.search(r'(?:项目|工程)', line_s):
                if not any(k in line_s for k in ['甲方', '乙方', '签订', '金额', '日期', '条款', '第', '付款', '质保', '保修', '期限', '价格', '地址']):
                    info['name'] = line_s
                    break
    # 4) 兜底：找含中文的短行
    if 'name' not in info:
        for line in text_lines:
            line_s = line.strip()
            if len(line_s) >= 4 and len(line_s) < 60 and not line_s.startswith('第'):
                cn_chars = len(re.findall(r'[\u4e00-\u9fa5]', line_s))
                if cn_chars >= 2:
                    info['name'] = line_s
                    break
    
    # =====================================================
    # 甲方 / 乙方（关键：公司名常跨多行！）
    # =====================================================
    party_a_keys = ['甲方', '买方', '发包方', '发包人', '委托方', '委托人', '需方', '采购方', '采购人', '招标方', '招标人', '出租方', '定作方', '出让方', '转让方', '授权方']
    party_b_keys = ['乙方', '卖方', '承包方', '承包人', '受托方', '受托人', '供方', '供应方', '供应商', '施工方', '施工人', '中标方', '中标人', '承租方', '承揽方', '受让方', '受权方', '被授权方']
    
    for i, line in enumerate(text_lines):
        if 'partyA' in info:
            break
        for key in party_a_keys:
            if key in line:
                # 去掉括号别名如"（买方）"，提取冒号后的内容
                clean = re.sub(r'[（(][^）)]*[）)]', '', line)
                m = re.search(rf'{re.escape(key)}\s*[：:]*\s*(.+)', clean)
                if m:
                    after = m.group(1).strip()
                    company = extract_company(after)
                    if company and len(company) > 2:
                        info['partyA'] = company
                        break
                    # 冒号后没有公司名？拼接后续行
                    if not after or len(after) <= 2:
                        joined = join_next_lines(i + 1, 3)
                        company = extract_company(joined)
                        if company:
                            info['partyA'] = company
                            break
                    # after本身可能是公司名一部分
                    if len(after) > 2:
                        joined = after + join_next_lines(i + 1, 2)
                        company = extract_company(joined)
                        if company:
                            info['partyA'] = company
                            break
    
    for i, line in enumerate(text_lines):
        if 'partyB' in info:
            break
        for key in party_b_keys:
            if key in line:
                clean = re.sub(r'[（(][^）)]*[）)]', '', line)
                m = re.search(rf'{re.escape(key)}\s*[：:]*\s*(.+)', clean)
                if m:
                    after = m.group(1).strip()
                    company = extract_company(after)
                    if company and len(company) > 2 and company != info.get('partyA', ''):
                        info['partyB'] = company
                        break
                    if not after or len(after) <= 2:
                        joined = join_next_lines(i + 1, 3)
                        company = extract_company(joined)
                        if company and company != info.get('partyA', ''):
                            info['partyB'] = company
                            break
                    if len(after) > 2:
                        joined = after + join_next_lines(i + 1, 2)
                        company = extract_company(joined)
                        if company and company != info.get('partyA', ''):
                            info['partyB'] = company
                            break
    
    # 底部签名区兜底："单位名称（盖章）：XXX公司"
    if 'partyA' not in info or 'partyB' not in info:
        for i, line in enumerate(text_lines):
            if '单位名称' in line or '盖章' in line:
                m = re.search(r'[：:]\s*(.+)', line)
                if m:
                    company = extract_company(m.group(1))
                    if company:
                        if 'partyA' not in info:
                            info['partyA'] = company
                        elif 'partyB' not in info and company != info.get('partyA', ''):
                            info['partyB'] = company
    
    # =====================================================
    # 合同金额（优先找明确关键词行，支持跨行匹配）
    # =====================================================
    amount_keys_strict = ['合同金额', '合同价', '合同总价', '合同价格', '合同价款', '总价款', '总金额', '承包金额', '优惠后总计']
    amount_keys_loose = ['金额', '总价', '价款', '合同总', '总价格', '含税', '不含税', '含税价', '价税', '货款', '工程款', '服务费', '费用', '报酬', '价格', '委托费用', '咨询服务费', '开发费']
    
    def find_amount_nearby(lines, start_idx, max_gap=4):
        """从start_idx行开始，在本行及后续max_gap行内查找金额"""
        for j in range(start_idx, min(start_idx + max_gap, len(lines))):
            val = extract_amount(lines[j])
            if val and val > 0:
                return val
        return None
    
    # 严格关键词匹配（含跨行）
    for i, line in enumerate(text_lines):
        if any(k in line for k in amount_keys_strict):
            val = extract_amount(line)
            if val and val > 0:
                info['amount'] = val
                break
            # 关键词和金额可能间隔多行（表格布局常见）
            val = find_amount_nearby(text_lines, i+1, 4)
            if val:
                info['amount'] = val
                break
    # 宽松关键词
    if 'amount' not in info:
        for i, line in enumerate(text_lines):
            if any(k in line for k in amount_keys_loose) or '人民币' in line or '¥' in line or '￥' in line:
                val = extract_amount(line)
                if val and val > 0:
                    info['amount'] = val
                    break
                val = find_amount_nearby(text_lines, i+1, 4)
                if val:
                    info['amount'] = val
                    break
    # "小写"金额行（政府采购合同常见格式："合同金额小写：¥1,250,330.40元"）
    if 'amount' not in info:
        for i, line in enumerate(text_lines):
            if '小写' in line:
                val = extract_amount(line)
                if val and val > 0:
                    info['amount'] = val
                    break
                # "小写"和金额可能跨行
                val = find_amount_nearby(text_lines, i+1, 3)
                if val:
                    info['amount'] = val
                    break
    # 全文正则兜底：合并所有行查找金额
    if 'amount' not in info:
        # 先尝试全文拼接后提取（处理关键词和金额被OCR拆成多段的情况）
        joined = re.sub(r'\s+', '', full_text)
        m = re.search(r'合同金额[^¥￥\d]*[¥￥]?\s*(\d[\d,，]*\.?\d*)', joined)
        if m:
            s = m.group(1).replace(',', '').replace('，', '')
            try:
                val = float(s)
                if val > 100:
                    info['amount'] = val
            except:
                pass
    if 'amount' not in info:
        for line in text_lines:
            if '元' in line or '万' in line:
                val = extract_amount(line)
                if val and val > 100:
                    info['amount'] = val
                    break
    if 'amount' not in info:
        for line in text_lines:
            val = extract_amount(line)
            if val and val > 100:
                info['amount'] = val
                break
    
    # =====================================================
    # 签订日期（关键词和日期可能分行！）
    # =====================================================
    sign_keys = ['签订', '签署', '订立', '签定', '签约', '签署日期', '签订日期', '合同日期', '签章日期', '生效日期', '签约日期', '签订时间']
    for i, line in enumerate(text_lines):
        if any(k in line for k in sign_keys):
            d = extract_date(line)
            if d:
                info['signDate'] = d
                break
            # 日期可能在下一行
            if i + 1 < len(text_lines):
                d = extract_date(text_lines[i + 1])
                if d:
                    info['signDate'] = d
                    break
    
    # =====================================================
    # 开始日期 / 结束日期
    # =====================================================
    if 'startDate' not in info:
        start_keys = ['开工', '起始', '开始日期', '实施日期', '开工日期', '起始日期', '起始时间', '起期']
        for i, line in enumerate(text_lines):
            if any(k in line for k in start_keys):
                d = extract_date(line)
                if d:
                    info['startDate'] = d
                    break
                if i + 1 < len(text_lines):
                    d = extract_date(text_lines[i + 1])
                    if d:
                        info['startDate'] = d
                        break
        if 'startDate' not in info:
            for line in text_lines:
                m = re.search(r'自\s*(\d{4})\s*[-年/\.]\s*(\d{1,2})\s*[-月/\.]\s*(\d{1,2})\s*日?\s*起', line)
                if m:
                    try:
                        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        if 2000 <= y <= 2100:
                            info['startDate'] = f'{y}-{mo:02d}-{d:02d}'
                            break
                    except:
                        pass
    
    if 'endDate' not in info:
        end_keys = ['竣工', '截止', '结束日期', '完成日期', '交付日期', '终止日期', '竣工日期', '截止日期', '结束时间', '止期']
        for i, line in enumerate(text_lines):
            if any(k in line for k in end_keys):
                d = extract_date(line)
                if d:
                    info['endDate'] = d
                    break
                if i + 1 < len(text_lines):
                    d = extract_date(text_lines[i + 1])
                    if d:
                        info['endDate'] = d
                        break
        if 'endDate' not in info:
            for line in text_lines:
                m = re.search(r'[至到]\s*(\d{4})\s*[-年/\.]\s*(\d{1,2})\s*[-月/\.]\s*(\d{1,2})\s*日?\s*(?:止|期|$)', line)
                if m:
                    try:
                        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        if 2000 <= y <= 2100:
                            info['endDate'] = f'{y}-{mo:02d}-{d:02d}'
                            break
                    except:
                        pass
    
    # =====================================================
    # 质保期（关键词和数字可能分行！）
    # =====================================================
    warranty_keys = ['质保', '保修', '质量保证', '质量保修', '质量保障', '售后', '维保', '质量保证期', '保修期', '质保期']
    cn_num_map = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'十一':11,'十二':12}
    def parse_warranty_period(text):
        """从文本提取质保期数，支持中文数字"""
        m = re.search(r'(\d+)\s*年\s*(\d+)\s*个月?', text)
        if m:
            return int(m.group(1)) * 12 + int(m.group(2))
        # 中文数字+年/月
        m = re.search(r'([一二两三四五六七八九十]+)\s*(年|个月|月)', text)
        if m:
            val = cn_num_map.get(m.group(1), 0)
            if val > 0:
                if '月' in m.group(2) or '个月' in m.group(2):
                    return val
                else:
                    return val * 12
        # 阿拉伯数字+年/月
        m = re.search(r'(\d+)\s*(年|个月|月)', text)
        if m:
            val = int(m.group(1))
            if '月' in m.group(2) or '个月' in m.group(2):
                return val
            else:
                return val * 12
        return None
    
    for i, line in enumerate(text_lines):
        if any(k in line for k in warranty_keys):
            # 本行搜索
            wm = parse_warranty_period(line)
            if wm:
                info['warrantyMonths'] = wm
                break
            # 下一行搜索
            if i + 1 < len(text_lines):
                wm = parse_warranty_period(text_lines[i + 1])
                if wm:
                    info['warrantyMonths'] = wm
                    break
            # 拼接本行+下一行搜索
            if i + 1 < len(text_lines):
                wm = parse_warranty_period(line + text_lines[i + 1])
                if wm:
                    info['warrantyMonths'] = wm
                    break
    
    # =====================================================
    # 质保金（关键词和金额可能分行！）
    # =====================================================
    deposit_keys = ['质保金', '保修金', '质量保证金', '保证金', '保留金', '质保金金额', '履约保证金', '履约保证金金额', '收取履约保证金', '履约保证金金额']
    for i, line in enumerate(text_lines):
        if any(k in line for k in deposit_keys):
            # 本行找金额
            val = extract_amount(line)
            if val and val > 0:
                info['warrantyDeposit'] = val
                break
            # 后续4行内查找金额
            val = find_amount_nearby(text_lines, i+1, 4)
            if val and val > 0:
                info['warrantyDeposit'] = val
                break
    # 兜底：找"X%质保金"或"质保金X%"的百分比，按合同金额算
    if 'warrantyDeposit' not in info and 'amount' in info:
        for i, line in enumerate(text_lines):
            if any(k in line for k in deposit_keys):
                m = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
                if m:
                    pct = float(m.group(1))
                    if 0 < pct <= 100:
                        info['warrantyDeposit'] = round(info['amount'] * pct / 100, 2)
                        break
    
    # =====================================================
    # 质保金回收日期
    # =====================================================
    deposit_return_keys = ['质保金.*(?:退|返|还|回收|返还|退还|归还)', '保证金.*(?:退|返|还|回收|返还|退还)', '保修金.*(?:退|返|还|回收|返还|退还)']
    for i, line in enumerate(text_lines):
        if any(re.search(k, line) for k in deposit_return_keys):
            d = extract_date(line)
            if d:
                info['warrantyDepositDate'] = d
                break
            if i + 1 < len(text_lines):
                d = extract_date(text_lines[i + 1])
                if d:
                    info['warrantyDepositDate'] = d
                    break
    
    # =====================================================
    # 兜底：从所有日期中补充
    # =====================================================
    used_dates = set()
    for k in ['signDate', 'startDate', 'endDate']:
        if k in info:
            used_dates.add(info[k])
    
    remaining_dates = []
    for line in text_lines:
        for d in extract_all_dates(line):
            if d not in remaining_dates:
                remaining_dates.append(d)
    
    available = [d for d in remaining_dates if d not in used_dates]
    if 'signDate' not in info and len(available) >= 1:
        info['signDate'] = available[0]
    if 'startDate' not in info and len(available) >= 2:
        info['startDate'] = available[1]
    if 'endDate' not in info and len(available) >= 3:
        info['endDate'] = available[2]
    
    if 'signDate' in info and 'endDate' in info and 'startDate' not in info:
        info['startDate'] = info['signDate']
    
    info['rawText'] = full_text
    return info

# === 配置 ===
# PyInstaller打包后：资源文件在sys._MEIPASS临时目录，数据文件在exe同目录
if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = sys._MEIPASS          # 打包资源目录（static、json等）
    _EXE_DIR = os.path.dirname(sys.executable)  # exe所在目录（持久数据）
else:
    _BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    _EXE_DIR = _BUNDLE_DIR

# 读取config.json（优先从exe同目录读，便于用户修改）
def _load_config():
    cfg_path = os.path.join(_EXE_DIR, 'config.json')
    if not os.path.exists(cfg_path):
        cfg_path = os.path.join(_BUNDLE_DIR, 'config.json')
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'[警告] 读取config.json失败: {e}，使用默认配置')
    return {}

_APP_CONFIG = _load_config()
HOST = _APP_CONFIG.get('host', '0.0.0.0')
PORT = _APP_CONFIG.get('port', 8199)
OPEN_BROWSER = _APP_CONFIG.get('open_browser', True)
MINIMIZE_TO_TRAY = _APP_CONFIG.get('minimize_to_tray', False)

BASE_DIR = _EXE_DIR
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'wfhelper.db')
FILES_DIR = os.path.join(DATA_DIR, 'files')
STAMPS_DIR = os.path.join(DATA_DIR, 'stamps')
STATIC_DIR = os.path.join(_BUNDLE_DIR, 'static')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(STAMPS_DIR, exist_ok=True)

# === 印章PNG处理辅助 ===
def _prepare_stamp_image(stamp_path):
    """将印章图片转为PyMuPDF可可靠插入的格式。
    策略：PIL统一转RGBA PNG，再用BytesIO输出bytes。
    返回 (png_bytes, img_width, img_height)
    """
    from PIL import Image as _PIL
    import io as _io
    pil = _PIL.open(stamp_path).convert('RGBA')
    buf = _io.BytesIO()
    pil.save(buf, 'PNG')
    buf.seek(0)
    png_bytes = buf.read()
    return png_bytes, pil.size[0], pil.size[1]

def _generate_contract_no(conn):
    """生成合同编号：YC-YYYYMMDD-序号（每日递增）"""
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    key = f'wfhelper_contract_no_{today}'
    row = conn.execute("SELECT value FROM kv_store WHERE key=?", (key,)).fetchone()
    seq = 1
    if row:
        seq = int(row['value']) + 1
    conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, str(seq)))
    conn.commit()
    return f'YC-{today}-{seq:03d}'

def _prepare_stamp_strip(pil_img, x0, x1):
    """将印章裁切条转为PyMuPDF可可靠插入的格式。
    返回 png_bytes
    """
    import io as _io
    # 确保裁切范围不超出图片
    x0 = max(0, int(x0))
    x1 = min(pil_img.size[0], int(x1))
    if x0 >= x1:
        x0 = max(0, x1 - 1)
    strip = pil_img.crop((x0, 0, x1, pil_img.size[1]))
    buf = _io.BytesIO()
    strip.save(buf, 'PNG')
    buf.seek(0)
    return buf.read()

# === 数据库 ===
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS kv_store (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    
    # Seed preset customers — 首次运行 或 数据丢失时自动恢复
    _need_preset = not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_preset_loaded'").fetchone()
    if not _need_preset:
        # 标记存在但数据为空→也重新加载（防止覆盖安装后数据丢失）
        _row = conn.execute("SELECT value FROM kv_store WHERE key='wfhelper_data'").fetchone()
        if not _row or not json.loads(_row['value']):
            _need_preset = True
            conn.execute("DELETE FROM kv_store WHERE key='wfhelper_preset_loaded'")
            conn.execute("DELETE FROM kv_store WHERE key='wfhelper_extra_loaded'")
    if _need_preset:
        preset_path = os.path.join(_BUNDLE_DIR, 'preset_customers.json')
        if os.path.exists(preset_path):
            with open(preset_path, 'r', encoding='utf-8') as f:
                customers = json.load(f)
            conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                        ('wfhelper_data', json.dumps(customers, ensure_ascii=False)))
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_preset_loaded', '"v2"'))
    
    # Seed extra customers — 同样做完整性检查
    _need_extra = not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_extra_loaded'").fetchone()
    if _need_extra:
        extra_path = os.path.join(_BUNDLE_DIR, 'extra_customers.json')
        if os.path.exists(extra_path):
            with open(extra_path, 'r', encoding='utf-8') as f:
                extra = json.load(f)
            row = conn.execute("SELECT value FROM kv_store WHERE key='wfhelper_data'").fetchone()
            existing = json.loads(row['value']) if row else []
            exist_phones = {c['phone'] for c in existing}
            to_add = [c for c in extra if c['phone'] not in exist_phones]
            merged = existing + to_add
            conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                        ('wfhelper_data', json.dumps(merged, ensure_ascii=False)))
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_extra_loaded', '"v2"'))
    
    # Seed default config
    if not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_config'").fetchone():
        default_config = {'dailyLimit': 25, 'retryDays': 3, 'myTitle': '悦动双成-展厅中控'}
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_config', json.dumps(default_config, ensure_ascii=False)))
    
    # Seed default templates
    if not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_templates'").fetchone():
        default_templates = [
            {'source':'展会','industry':'','remark':'{MyTitle}，{Source}展会','greeting':'{Name}总您好，{Source}展会上了解到贵司有展厅项目，我们做展厅中控系统，价格优、专业可靠，售后服务至善至上，方便发您参考吗？'},
            {'source':'同行介绍','industry':'','remark':'{MyTitle}，{Referrer}推荐','greeting':'{Name}总您好，听{Referrer}提到贵司在做展厅项目，我们专注展厅中控系统，性价比高、专业靠谱，售后至善至上，加您发些案例'},
            {'source':'行业筛选','industry':'','remark':'{MyTitle}，展厅中控咨询','greeting':'{Name}总您好，看到贵司在展厅方向有业务，我们做展厅中控产品，价格优、专业强、售后至善至上，加个微信交流下？'},
            {'source':'其他','industry':'','remark':'{MyTitle}','greeting':'{Name}总您好，我是做展厅中控的，价格优、专业可靠、售后至善至上，想跟您交流下，方便吗？'},
            {'source':'展会','industry':'展览展示','remark':'{MyTitle}，{Source}展会','greeting':'{Name}总您好，{Source}展会上了解到贵司做展览展示，我们专注展厅中控系统，价格优、专业可靠、售后至善至上，有不少案例可以分享'},
            {'source':'行业筛选','industry':'博物馆','remark':'{MyTitle}，博物馆中控方案','greeting':'{Name}总您好，了解到贵司有博物馆项目，我们在展厅中控方面经验丰富，价格优、专业强、售后至善至上，方便交流下吗？'},
            {'source':'行业筛选','industry':'科技馆','remark':'{MyTitle}，科技馆中控方案','greeting':'{Name}总您好，了解到贵司有科技馆项目，我们在展厅中控方面经验丰富，价格优、专业强、售后至善至上，方便交流下吗？'},
            {'source':'行业筛选','industry':'企业展厅','remark':'{MyTitle}，企业展厅中控方案','greeting':'{Name}总您好，了解到贵司有企业展厅项目，我们做展厅中控系统，价格优、专业可靠、售后至善至上，加您发些案例？'}
        ]
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_templates', json.dumps(default_templates, ensure_ascii=False)))
    
    # Initialize empty contracts
    if not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_contracts'").fetchone():
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_contracts', '[]'))
    
    # Initialize empty maint records
    if not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_maint_items'").fetchone():
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_maint_items', '[]'))
    if not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_maint_records'").fetchone():
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_maint_records', '[]'))
    if not conn.execute("SELECT 1 FROM kv_store WHERE key='wfhelper_maint_notes'").fetchone():
        conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    ('wfhelper_maint_notes', '[]'))
    
    conn.commit()
    conn.close()

# === HTTP 处理器 ===
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging
    
    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def send_text(self, text, content_type='text/plain; charset=utf-8', code=200):
        body = text.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def send_file(self, filepath, download_name=None, inline=False, mime_type=None):
        if not os.path.exists(filepath):
            self.send_error(404, 'File not found')
            return
        if mime_type:
            mime = mime_type
        else:
            mime, _ = mimetypes.guess_type(filepath)
            if not mime:
                mime = 'application/octet-stream'
        size = os.path.getsize(filepath)
        self.send_response(200)
        # 图片和PDF不加charset
        if mime.startswith('image/') or mime == 'application/pdf':
            self.send_header('Content-Type', mime)
        else:
            self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.send_header('Content-Length', str(size))
        if inline:
            self.send_header('Content-Disposition', 'inline')
        elif download_name:
            self.send_header('Content-Disposition', f'attachment; filename="{download_name}"')
        self.end_headers()
        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())
    
    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length > 0 else b''
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # API: GET /api/data/<key>
        if path.startswith('/api/data/'):
            key = path[len('/api/data/'):]
            conn = get_db()
            row = conn.execute("SELECT value FROM kv_store WHERE key=?", (key,)).fetchone()
            conn.close()
            if row:
                self.send_text(row['value'], 'application/json; charset=utf-8')
            else:
                self.send_text('null', 'application/json; charset=utf-8')
            return
        
        # API: GET /api/ocr-test - 测试百度OCR连通性
        if path == '/api/ocr-test':
            token = get_bd_access_token()
            if token:
                self.send_json({'ok': True, 'message': '百度OCR连接正常，token已获取', 'token_preview': token[:8] + '...'})
            else:
                self.send_json({'ok': False, 'error': _bd_token_error or '未知错误'})
            return
        
        # API: GET /api/files/<fid>
        if path.startswith('/api/files/'):
            fid = path[len('/api/files/'):]
            if '/' in fid or '\\' in fid or fid.startswith('.'):
                self.send_json({'error': 'Invalid ID'}, 400)
                return
            filepath = os.path.join(FILES_DIR, fid)
            if not os.path.exists(filepath):
                self.send_json({'error': 'Not found'}, 404)
                return
            params = urllib.parse.parse_qs(parsed.query)
            name = params.get('name', [fid])[0]
            mimetype = params.get('type', ['application/octet-stream'])[0]
            if mimetype.startswith('image/') or mimetype == 'application/pdf':
                self.send_file(filepath, download_name=None, inline=True, mime_type=mimetype)
            else:
                self.send_file(filepath, name)
            return
        
        # API: GET /api/pdf-pages/<fid> - 获取PDF各页缩略图（服务端缓存）
        if path.startswith('/api/pdf-pages/'):
            fid = path[len('/api/pdf-pages/'):]
            if '/' in fid or '\\' in fid or fid.startswith('.'):
                self.send_json({'error': 'Invalid ID'}, 400)
                return
            filepath = os.path.join(FILES_DIR, fid)
            if not os.path.exists(filepath):
                self.send_json({'error': 'File not found'}, 404)
                return
            try:
                import fitz
                pages_dir = os.path.join(FILES_DIR, 'pages', fid)
                # 检查是否已有缓存（文件未修改）
                src_mtime = os.path.getmtime(filepath)
                cache_marker = os.path.join(pages_dir, '.cache_ok')
                use_cache = False
                if os.path.exists(cache_marker):
                    try:
                        cache_mtime = os.path.getmtime(cache_marker)
                        if cache_mtime >= src_mtime:
                            use_cache = True
                    except:
                        pass
                if use_cache:
                    # 直接从缓存目录读取页面列表
                    pages = []
                    for fn in sorted(os.listdir(pages_dir)):
                        if fn.startswith('page_') and fn.endswith('.jpg'):
                            pn = int(fn.replace('page_','').replace('.jpg',''))
                            pages.append({'page': pn, 'url': f'/api/pdf-page-img/{fid}/{fn}'})
                    pages.sort(key=lambda x: x['page'])
                    if pages:
                        self.send_json({'pages': pages, 'total': len(pages)})
                        return
                # 需要渲染
                doc = fitz.open(filepath)
                pages = []
                os.makedirs(pages_dir, exist_ok=True)
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    pix = page.get_pixmap(dpi=120)
                    page_filename = f'page_{page_num+1}.jpg'
                    page_path = os.path.join(pages_dir, page_filename)
                    pix.save(page_path)
                    pages.append({'page': page_num+1, 'url': f'/api/pdf-page-img/{fid}/{page_filename}'})
                doc.close()
                # 标记缓存完成
                with open(cache_marker, 'w') as f:
                    f.write(str(src_mtime))
                self.send_json({'pages': pages, 'total': len(pages)})
            except ImportError:
                self.send_json({'error': '需要安装PyMuPDF: pip install pymupdf'}, 500)
            except Exception as e:
                self.send_json({'error': f'PDF页面渲染失败: {e}'}, 500)
            return
        
        # API: GET /api/pdf-page-preview/<fid>/<page_num> - 获取PDF单页预览图（用于盖章拖拽）
        if path.startswith('/api/pdf-page-preview/'):
            parts = path[len('/api/pdf-page-preview/'):]
            parts = parts.split('/')
            if len(parts) < 2:
                self.send_json({'error': 'Invalid path'}, 400); return
            fid, page_num_str = parts[0], parts[1]
            if '/' in fid or '\\' in fid or fid.startswith('.'):
                self.send_json({'error': 'Invalid ID'}, 400); return
            try:
                page_num = int(page_num_str)
            except:
                self.send_json({'error': 'Invalid page'}, 400); return
            filepath = os.path.join(FILES_DIR, fid)
            if not os.path.exists(filepath):
                self.send_json({'error': 'File not found'}, 404); return
            try:
                import fitz
                doc = fitz.open(filepath)
                if page_num < 1 or page_num > len(doc):
                    doc.close()
                    self.send_json({'error': 'Page out of range'}, 400); return
                page = doc[page_num - 1]
                pix = page.get_pixmap(dpi=150)
                import io
                img_bytes = pix.tobytes('png')
                doc.close()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', len(img_bytes))
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(img_bytes)
            except ImportError:
                self.send_json({'error': '需要安装PyMuPDF'}, 500)
            except Exception as e:
                self.send_json({'error': f'渲染失败: {e}'}, 500)
            return
        
        # API: GET /api/pdf-page-img/<fid>/<filename> - 返回PDF某页的图片
        if path.startswith('/api/pdf-page-img/'):
            parts = path[len('/api/pdf-page-img/'):]
            if '/' not in parts:
                self.send_json({'error': 'Invalid path'}, 400)
                return
            fid, filename = parts.split('/', 1)
            if '/' in fid or '\\' in fid or fid.startswith('.') or '..' in filename:
                self.send_json({'error': 'Invalid path'}, 400)
                return
            img_path = os.path.join(FILES_DIR, 'pages', fid, filename)
            if not os.path.exists(img_path):
                self.send_json({'error': 'Image not found'}, 404)
                return
            self.send_file(img_path, inline=True)
            return

        # API: GET /api/stamps - 获取印章列表
        if path == '/api/stamps':
            stamps = []
            if os.path.exists(STAMPS_DIR):
                for fn in sorted(os.listdir(STAMPS_DIR)):
                    if fn.endswith(('.png','.jpg','.jpeg')) and not fn.startswith('.'):
                        fp = os.path.join(STAMPS_DIR, fn)
                        stamps.append({'id': fn, 'name': fn.rsplit('.',1)[0], 'url': f'/api/stamp-img/{fn}'})
            self.send_json({'stamps': stamps})
            return
        
        # API: GET /api/stamp-img/<filename> - 返回印章图片
        if path.startswith('/api/stamp-img/'):
            fn = urllib.parse.unquote(path[len('/api/stamp-img/'):])
            if '/' in fn or '\\' in fn or fn.startswith('.'):
                self.send_json({'error': 'Invalid'}, 400); return
            img_path = os.path.join(STAMPS_DIR, fn)
            if not os.path.exists(img_path):
                self.send_json({'error': 'Not found'}, 404); return
            self.send_file(img_path, inline=True)
            return

        # API: GET /api/export
        if path == '/api/export':
            conn = get_db()
            rows = conn.execute("SELECT key, value FROM kv_store").fetchall()
            conn.close()
            data = {row['key']: json.loads(row['value']) for row in rows}
            self.send_json(data)
            return
        
        # Static files
        if path == '/':
            path = '/index.html'
        
        # Security: prevent directory traversal
        safe_path = os.path.normpath(path).lstrip('/').lstrip('\\')
        filepath = os.path.join(STATIC_DIR, safe_path)
        if not os.path.realpath(filepath).startswith(os.path.realpath(STATIC_DIR)):
            self.send_error(403)
            return
        
        if os.path.isfile(filepath):
            self.send_file(filepath)
        else:
            self.send_error(404)
    
    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # API: PUT /api/data/<key>
        if path.startswith('/api/data/'):
            key = path[len('/api/data/'):]
            body = self.read_body().decode('utf-8')
            conn = get_db()
            conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, body))
            conn.commit()
            conn.close()
            self.send_json({'ok': True})
            return
        
        self.send_error(404)
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # API: POST /api/files/upload
        if path == '/api/files/upload':
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json({'error': 'Expected multipart/form-data'}, 400)
                return
            
            # Parse boundary
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[len('boundary='):]
                    break
            if not boundary:
                self.send_json({'error': 'No boundary'}, 400)
                return
            
            body = self.read_body()
            
            # Simple multipart parser
            boundary_bytes = boundary.encode()
            parts = body.split(b'--' + boundary_bytes)
            
            file_data = None
            file_name = ''
            file_type = 'application/octet-stream'
            thumbnail = ''
            
            for part in parts:
                if not part or part.strip() == b'--' or part.strip() == b'':
                    continue
                # Find headers end
                header_end = part.find(b'\r\n\r\n')
                if header_end < 0:
                    continue
                headers_raw = part[:header_end].decode('utf-8', errors='replace')
                content = part[header_end + 4:]
                
                # Remove trailing \r\n
                if content.endswith(b'\r\n'):
                    content = content[:-2]
                
                # Parse Content-Disposition
                name = ''
                filename = ''
                for line in headers_raw.split('\r\n'):
                    if line.lower().startswith('content-disposition:'):
                        for item in line.split(';'):
                            item = item.strip()
                            if item.startswith('name='):
                                name = item[len('name='):].strip('"')
                            elif item.startswith('filename='):
                                filename = item[len('filename='):].strip('"')
                    elif line.lower().startswith('content-type:'):
                        file_type = line.split(':', 1)[1].strip()
                
                if name == 'file' and filename:
                    file_data = content
                    file_name = filename
                elif name == 'thumbnail' and not filename:
                    thumbnail = content.decode('utf-8', errors='replace')
            
            if file_data is None:
                self.send_json({'error': 'No file data'}, 400)
                return
            
            fid = uuid.uuid4().hex[:12]
            save_path = os.path.join(FILES_DIR, fid)
            with open(save_path, 'wb') as f:
                f.write(file_data)
            
            self.send_json({
                'id': fid,
                'name': file_name,
                'type': file_type,
                'size': len(file_data),
                'thumbnail': thumbnail
            })
            return
        
        # API: POST /api/stamps/upload - 上传印章图片
        if path == '/api/stamps/upload':
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json({'error': 'Expected multipart/form-data'}, 400); return
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[len('boundary='):]; break
            if not boundary:
                self.send_json({'error': 'No boundary'}, 400); return
            body = self.read_body()
            boundary_bytes = boundary.encode()
            parts = body.split(b'--' + boundary_bytes)
            file_data = None; file_name = ''; stamp_name = ''
            for part in parts:
                if not part or part.strip() == b'--' or part.strip() == b'': continue
                header_end = part.find(b'\r\n\r\n')
                if header_end < 0: continue
                headers_raw = part[:header_end].decode('utf-8', errors='replace')
                content = part[header_end + 4:]
                if content.endswith(b'\r\n'): content = content[:-2]
                name = ''; filename = ''
                for line in headers_raw.split('\r\n'):
                    if line.lower().startswith('content-disposition:'):
                        for item in line.split(';'):
                            item = item.strip()
                            if item.startswith('name='): name = item[len('name='):].strip('"')
                            elif item.startswith('filename='): filename = item[len('filename='):].strip('"')
                if name == 'file' and filename:
                    file_data = content; file_name = filename
                elif name == 'name' and not filename:
                    stamp_name = content.decode('utf-8', errors='replace').strip()
            if file_data is None:
                self.send_json({'error': 'No file data'}, 400); return
            # 生成文件名
            if not stamp_name: stamp_name = file_name.rsplit('.',1)[0]
            ext = file_name.rsplit('.',1)[-1] if '.' in file_name else 'png'
            safe_name = re.sub(r'[^\w\u4e00-\u9fff-]','_', stamp_name)
            save_fn = f'{safe_name}.{ext}'
            # 避免重名
            i = 1; base_fn = save_fn
            while os.path.exists(os.path.join(STAMPS_DIR, save_fn)):
                save_fn = f'{safe_name}_{i}.{ext}'; i += 1
            with open(os.path.join(STAMPS_DIR, save_fn), 'wb') as f:
                f.write(file_data)
            self.send_json({'ok': True, 'id': save_fn, 'name': stamp_name, 'url': f'/api/stamp-img/{save_fn}'})
            return
        
        # API: POST /api/restore-preset - 手动恢复预设客户数据（合并，不覆盖已有）
        if path == '/api/restore-preset':
            try:
                conn = get_db()
                # 读取已有客户数据
                row = conn.execute("SELECT value FROM kv_store WHERE key='wfhelper_data'").fetchone()
                existing = json.loads(row['value']) if row else []
                exist_phones = {c.get('phone','') for c in existing}
                exist_ids = {c.get('id','') for c in existing}
                
                # 加载preset
                preset_path = os.path.join(_BUNDLE_DIR, 'preset_customers.json')
                added = 0
                if os.path.exists(preset_path):
                    with open(preset_path, 'r', encoding='utf-8') as f:
                        preset = json.load(f)
                    for c in preset:
                        if c.get('phone','') not in exist_phones and c.get('id','') not in exist_ids:
                            existing.append(c)
                            exist_phones.add(c.get('phone',''))
                            exist_ids.add(c.get('id',''))
                            added += 1
                
                # 加载extra
                extra_path = os.path.join(_BUNDLE_DIR, 'extra_customers.json')
                if os.path.exists(extra_path):
                    with open(extra_path, 'r', encoding='utf-8') as f:
                        extra = json.load(f)
                    for c in extra:
                        if c.get('phone','') not in exist_phones and c.get('id','') not in exist_ids:
                            existing.append(c)
                            exist_phones.add(c.get('phone',''))
                            exist_ids.add(c.get('id',''))
                            added += 1
                
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                            ('wfhelper_data', json.dumps(existing, ensure_ascii=False)))
                # 设置标记以防init_db重复加载
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                            ('wfhelper_preset_loaded', '"v2"'))
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                            ('wfhelper_extra_loaded', '"v2"'))
                conn.commit()
                self.send_json({'ok': True, 'count': len(existing), 'added': added})
            except Exception as e:
                self.send_json({'ok': False, 'error': str(e)}, 500)
            return

        # API: POST /api/stamp-apply - 给PDF盖公章或骑缝章
        if path == '/api/stamp-apply':
            body = self.read_body().decode('utf-8')
            try:
                params = json.loads(body)
            except:
                self.send_json({'error': 'Invalid JSON'}, 400); return
            fid = params.get('fid', '')
            stamp_id = params.get('stampId', '')
            stamp_type = params.get('type', 'seal')  # seal=公章, cross=骑缝章
            page_num = params.get('page', 1)  # 公章盖在哪一页
            # 位置参数（归一化0~1）
            pos_x = params.get('x', 0.72)  # 公章X位置
            pos_y = params.get('y', 0.82)  # 公章Y位置
            stamp_scale = params.get('scale', 0.18)  # 印章占页面宽度比例
            cross_y = params.get('crossY', 0.5)  # 骑缝章Y位置（归一化0~1）
            if '/' in fid or '\\' in fid or fid.startswith('.'):
                self.send_json({'error': 'Invalid fid'}, 400); return
            if '/' in stamp_id or '\\' in stamp_id or stamp_id.startswith('.'):
                self.send_json({'error': 'Invalid stamp'}, 400); return
            
            src_pdf = os.path.join(FILES_DIR, fid)
            stamp_img = os.path.join(STAMPS_DIR, stamp_id)
            if not os.path.exists(src_pdf):
                self.send_json({'error': 'PDF文件不存在'}, 404); return
            if not os.path.exists(stamp_img):
                self.send_json({'error': '印章图片不存在'}, 404); return
            if not src_pdf.lower().endswith('.pdf') and open(src_pdf,'rb').read(5) != b'%PDF-':
                self.send_json({'error': '仅支持PDF文件盖章'}, 400); return
            
            try:
                import fitz
                doc = fitz.open(src_pdf)
                
                total_pages = len(doc)
                
                if stamp_type == 'seal':
                    # 公章：盖在指定页面的指定位置
                    pg = min(int(page_num) - 1, total_pages - 1)
                    page = doc[pg]
                    pw, ph = page.rect.width, page.rect.height
                    sw = pw * stamp_scale
                    _png_bytes, _img_w, _img_h = _prepare_stamp_image(stamp_img)
                    sh = sw * (_img_h / _img_w) if _img_w > 0 else sw
                    sx = pw * pos_x - sw / 2
                    sy = ph * pos_y - sh / 2
                    rect = fitz.Rect(sx, sy, sx + sw, sy + sh)
                    page.insert_image(rect, stream=_png_bytes, overlay=True)
                elif stamp_type == 'cross':
                    # 骑缝章：模拟真实骑缝章
                    # 真实骑缝章：文件错开排列，公章盖在最后一页上并跨压缝隙，
                    # 每页都留有印章的一部分，防抽换
                    # 电子实现：完整印章按页数等分为N个竖条，每页右边缘放对应条
                    # 条宽 = max(完整印章宽度/页数, 页面宽度*2%)，确保可见
                    if total_pages < 2:
                        self.send_json({'error': '骑缝章至少需要2页'}, 400); return
                    from PIL import Image as PILImage
                    pil_img = PILImage.open(stamp_img).convert('RGBA')
                    img_w, img_h = pil_img.size
                    
                    for i in range(total_pages):
                        page = doc[i]
                        pw, ph = page.rect.width, page.rect.height
                        
                        # 完整印章在页面上的尺寸
                        full_stamp_w = pw * stamp_scale
                        full_stamp_h = full_stamp_w * (img_h / img_w) if img_w > 0 else full_stamp_w
                        
                        # 每页条的实际宽度：取等分宽度和最小可见宽度的较大值
                        min_visible_w = pw * 0.02  # 至少页面宽度的2%（A4约12pt≈4mm）
                        page_strip_w = max(full_stamp_w / total_pages, min_visible_w)
                        
                        # 该条在完整印章中的像素范围（等分）
                        px_x0 = i * (img_w / total_pages)
                        px_x1 = (i + 1) * (img_w / total_pages)
                        _strip_bytes = _prepare_stamp_strip(pil_img, px_x0, px_x1)
                        
                        # 条在PDF中的位置：右边缘，垂直居中
                        stamp_y = ph * cross_y - full_stamp_h / 2
                        stamp_x = pw - page_strip_w
                        rect = fitz.Rect(stamp_x, stamp_y, pw, stamp_y + full_stamp_h)
                        page.insert_image(rect, stream=_strip_bytes, overlay=True)
                elif stamp_type == 'both':
                    # 公章+骑缝章：先盖公章，再盖骑缝章，一次生成一个文件
                    # 1. 公章
                    pg = min(int(page_num) - 1, total_pages - 1)
                    page = doc[pg]
                    pw, ph = page.rect.width, page.rect.height
                    sw = pw * stamp_scale
                    _png_bytes, _img_w, _img_h = _prepare_stamp_image(stamp_img)
                    sh = sw * (_img_h / _img_w) if _img_w > 0 else sw
                    sx = pw * pos_x - sw / 2
                    sy = ph * pos_y - sh / 2
                    rect = fitz.Rect(sx, sy, sx + sw, sy + sh)
                    page.insert_image(rect, stream=_png_bytes, overlay=True)
                    # 2. 骑缝章（与cross模式逻辑一致）
                    if total_pages >= 2:
                        from PIL import Image as PILImage
                        pil_img = PILImage.open(stamp_img).convert('RGBA')
                        img_w, img_h = pil_img.size
                        for i in range(total_pages):
                            p = doc[i]
                            ppw, pph = p.rect.width, p.rect.height
                            full_stamp_w = ppw * stamp_scale
                            full_stamp_h = full_stamp_w * (img_h / img_w) if img_w > 0 else full_stamp_w
                            min_visible_w = ppw * 0.02
                            page_strip_w = max(full_stamp_w / total_pages, min_visible_w)
                            px_x0 = i * (img_w / total_pages)
                            px_x1 = (i + 1) * (img_w / total_pages)
                            _strip_bytes = _prepare_stamp_strip(pil_img, px_x0, px_x1)
                            stamp_y = pph * cross_y - full_stamp_h / 2
                            stamp_x = ppw - page_strip_w
                            r = fitz.Rect(stamp_x, stamp_y, ppw, stamp_y + full_stamp_h)
                            p.insert_image(r, stream=_strip_bytes, overlay=True)
                
                # 合同编号：每一页左下角小字标识，代表本软件生成
                _sconn = get_db()
                contract_no = _generate_contract_no(_sconn)
                _sconn.close()
                for i in range(total_pages):
                    p = doc[i]
                    pw, ph = p.rect.width, p.rect.height
                    try:
                        # 左下角，6pt极小字体，浅灰色
                        p.insert_text(
                            fitz.Point(20, ph - 12),
                            contract_no,
                            fontsize=6,
                            color=(0.7, 0.7, 0.7),  # 浅灰色
                            fontname="helv"
                        )
                    except Exception:
                        pass  # 编号插入失败不影响主流程
                
                # 保存为新文件（不覆盖原文件）
                # 文件名格式：原文件名_YYYYMMDD_HHMM【盖章.pdf
                original_name = params.get('fileName', fid)
                # 去掉路径只留文件名
                original_name = original_name.replace('\\', '/').rsplit('/', 1)[-1]
                name_base = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
                from datetime import datetime
                now = datetime.now()
                timestamp = now.strftime('%Y%m%d_%H%M')
                new_fid = f'{name_base}_{timestamp}【盖章.pdf'
                # 处理重名
                idx = 1
                while os.path.exists(os.path.join(FILES_DIR, new_fid)):
                    new_fid = f'{name_base}_{timestamp}【盖章_{idx}.pdf'
                    idx += 1
                # 清除旧的缩略图缓存
                new_cache = os.path.join(FILES_DIR, 'pages', new_fid)
                if os.path.exists(new_cache):
                    import shutil
                    shutil.rmtree(new_cache, ignore_errors=True)
                
                save_path = os.path.join(FILES_DIR, new_fid)
                doc.save(save_path)
                doc.close()
                
                new_size = os.path.getsize(save_path)
                
                # 复制到用户指定的保存路径
                save_dir = params.get('saveDir', '').strip()
                copied_to = ''
                if save_dir and os.path.isdir(save_dir):
                    try:
                        import shutil
                        dest = os.path.join(save_dir, new_fid)
                        shutil.copy2(save_path, dest)
                        copied_to = save_dir
                    except Exception as e:
                        print(f'[盖章] 复制到保存路径失败: {e}')
                
                result = {'ok': True, 'newFid': new_fid, 'newName': new_fid, 'size': new_size, 'pages': total_pages, 'contractNo': contract_no}
                if copied_to:
                    result['copiedTo'] = copied_to
                self.send_json(result)
            except ImportError:
                self.send_json({'error': '需要安装PyMuPDF: pip install pymupdf'}, 500)
            except Exception as e:
                self.send_json({'error': f'盖章失败: {e}'}, 500)
            return
        
        # API: POST /api/csv-import
        if path == '/api/csv-import':
            # Similar multipart parsing
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json({'error': 'Expected multipart/form-data'}, 400)
                return
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[len('boundary='):]
                    break
            if not boundary:
                self.send_json({'error': 'No boundary'}, 400)
                return
            
            body = self.read_body()
            boundary_bytes = boundary.encode()
            parts = body.split(b'--' + boundary_bytes)
            
            csv_content = ''
            for part in parts:
                if not part or part.strip() == b'--' or part.strip() == b'':
                    continue
                header_end = part.find(b'\r\n\r\n')
                if header_end < 0:
                    continue
                headers_raw = part[:header_end].decode('utf-8', errors='replace')
                content = part[header_end + 4:]
                if content.endswith(b'\r\n'):
                    content = content[:-2]
                
                if 'name="file"' in headers_raw:
                    # Try UTF-8 first, then GBK
                    try:
                        csv_content = content.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        csv_content = content.decode('gbk')
            
            if not csv_content:
                self.send_json({'error': 'No CSV data'}, 400)
                return
            
            lines = csv_content.split('\n')
            conn = get_db()
            row = conn.execute("SELECT value FROM kv_store WHERE key='wfhelper_data'").fetchone()
            customers = json.loads(row['value']) if row else []
            exist_phones = {c['phone'] for c in customers}
            
            imported = 0
            skipped = 0
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts_csv = [p.strip().strip('"') for p in line.split(',')]
                if len(parts_csv) < 2:
                    continue
                name_c, phone = parts_csv[0], parts_csv[1]
                if not name_c or not phone:
                    continue
                if phone in exist_phones:
                    skipped += 1
                    continue
                c = {
                    'id': uuid.uuid4().hex[:14],
                    'name': name_c, 'phone': phone,
                    'company': parts_csv[2] if len(parts_csv) > 2 else '',
                    'industry': parts_csv[3] if len(parts_csv) > 3 else '',
                    'source': parts_csv[4] if len(parts_csv) > 4 else '',
                    'status': 0, 'retryCount': 0, 'maxRetry': 3,
                    'createdAt': datetime.now().isoformat()
                }
                customers.append(c)
                exist_phones.add(phone)
                imported += 1
            
            conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                        ('wfhelper_data', json.dumps(customers, ensure_ascii=False)))
            conn.commit()
            conn.close()
            self.send_json({'imported': imported, 'skipped': skipped})
            return
        
        # API: POST /api/import
        if path == '/api/import':
            body = self.read_body().decode('utf-8')
            try:
                incoming = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({'error': 'Invalid JSON'}, 400)
                return
            
            conn = get_db()
            
            if 'customers' in incoming and incoming['customers']:
                row = conn.execute("SELECT value FROM kv_store WHERE key='wfhelper_data'").fetchone()
                existing = json.loads(row['value']) if row else []
                exist_map = {c['id']: c for c in existing}
                merged = []
                for c in incoming['customers']:
                    if c['id'] in exist_map:
                        ex = exist_map[c['id']]
                        if ex.get('status', 0) > 0 or ex.get('remark') or ex.get('greeting') or ex.get('avatarData'):
                            merged.append(ex)
                        else:
                            merged.append(c)
                    else:
                        merged.append(c)
                incoming_ids = {c['id'] for c in incoming['customers']}
                for c in existing:
                    if c['id'] not in incoming_ids:
                        merged.append(c)
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                            ('wfhelper_data', json.dumps(merged, ensure_ascii=False)))
            
            if 'config' in incoming:
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                            ('wfhelper_config', json.dumps(incoming['config'], ensure_ascii=False)))
            
            if 'templates' in incoming:
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                            ('wfhelper_templates', json.dumps(incoming['templates'], ensure_ascii=False)))
            
            if 'contracts' in incoming and incoming['contracts']:
                row = conn.execute("SELECT value FROM kv_store WHERE key='wfhelper_contracts'").fetchone()
                existing_c = json.loads(row['value']) if row else []
                exist_c_map = {c['id']: c for c in existing_c}
                merged_c = [exist_c_map.get(c['id'], c) for c in incoming['contracts']]
                incoming_c_ids = {c['id'] for c in incoming['contracts']}
                for c in existing_c:
                    if c['id'] not in incoming_c_ids:
                        merged_c.append(c)
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                            ('wfhelper_contracts', json.dumps(merged_c, ensure_ascii=False)))
            
            conn.commit()
            conn.close()
            self.send_json({'ok': True})
            return
        
        # API: POST /api/ocr - 合同图片/PDF OCR识别
        if path == '/api/ocr':
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_json({'error': 'Expected multipart/form-data'}, 400)
                return
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[len('boundary='):]
                    break
            if not boundary:
                self.send_json({'error': 'No boundary'}, 400)
                return
            
            body = self.read_body()
            boundary_bytes = boundary.encode()
            parts = body.split(b'--' + boundary_bytes)
            
            file_data = None
            file_name = ''
            for part in parts:
                if not part or part.strip() == b'--' or part.strip() == b'':
                    continue
                header_end = part.find(b'\r\n\r\n')
                if header_end < 0:
                    continue
                headers_raw = part[:header_end].decode('utf-8', errors='replace')
                content = part[header_end + 4:]
                if content.endswith(b'\r\n'):
                    content = content[:-2]
                if 'name="file"' in headers_raw:
                    file_data = content
                    for line in headers_raw.split('\r\n'):
                        if 'filename=' in line:
                            file_name = line.split('filename=')[-1].strip('"')
            
            if file_data is None:
                self.send_json({'error': 'No file data'}, 400)
                return
            
            # 判断是否为PDF
            is_pdf = file_name.lower().endswith('.pdf') or file_data[:5] == b'%PDF-'
            
            # 调用OCR（包裹try-except防止崩溃）
            try:
                words, err = ocr_recognize(file_data, is_pdf=is_pdf)
                if err:
                    detail = _bd_token_error if 'OCR服务未授权' in err else ''
                    self.send_json({'error': err + (' — ' + detail if detail else '')}, 500)
                    return
                contract_info = parse_contract_info(words)
                contract_info['ocrLines'] = words
                self.send_json(contract_info)
            except Exception as e:
                print(f'[OCR] 严重错误: {e}')
                self.send_json({'error': f'OCR处理异常: {e}'}, 500)
            return
        
        self.send_error(404)
    
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # API: DELETE /api/files/<fid>
        if path.startswith('/api/files/'):
            fid = path[len('/api/files/'):]
            if '/' in fid or '\\' in fid or fid.startswith('.'):
                self.send_json({'error': 'Invalid ID'}, 400)
                return
            filepath = os.path.join(FILES_DIR, fid)
            if os.path.exists(filepath):
                os.remove(filepath)
            # 清除缩略图缓存
            cache_dir = os.path.join(FILES_DIR, 'pages', fid)
            if os.path.exists(cache_dir):
                import shutil
                shutil.rmtree(cache_dir, ignore_errors=True)
            self.send_json({'ok': True})
            return
        
        # API: DELETE /api/stamps/<filename>
        if path.startswith('/api/stamps/'):
            fn = urllib.parse.unquote(path[len('/api/stamps/'):])
            if '/' in fn or '\\' in fn or fn.startswith('.'):
                self.send_json({'error': 'Invalid'}, 400); return
            fp = os.path.join(STAMPS_DIR, fn)
            if os.path.exists(fp):
                os.remove(fp)
            self.send_json({'ok': True})
            return
        
        self.send_error(404)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

def main():
    init_db()
    local_ip = get_local_ip()
    
    server = HTTPServer((HOST, PORT), Handler)
    
    print('=' * 50)
    print('  微信好友助手 v2.0 - 本地服务器版')
    print('=' * 50)
    print(f'  本机访问：http://localhost:{PORT}')
    print(f'  局域网访问：http://{local_ip}:{PORT}')
    print(f'  监听地址：{HOST}:{PORT}')
    print(f'  配置文件：config.json（可修改host/port）')
    print(f'  数据目录：{DATA_DIR}')
    if MINIMIZE_TO_TRAY:
        print(f'  托盘模式：已启用（最小化到系统托盘）')
    print(f'  按 Ctrl+C 停止服务器')
    print('=' * 50)
    
    # Open browser after a short delay
    if OPEN_BROWSER and not MINIMIZE_TO_TRAY:
        def open_browser():
            webbrowser.open(f'http://localhost:{PORT}')
        threading.Timer(1.5, open_browser).start()
    
    if MINIMIZE_TO_TRAY:
        _run_with_tray(server, PORT)
    else:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\n服务器已停止')
            server.server_close()

def _run_with_tray(server, port):
    """以系统托盘方式运行"""
    try:
        import pystray
        from PIL import Image as PILImage
    except ImportError:
        print('[警告] pystray未安装，无法最小化到托盘，以普通模式运行')
        print('[提示] 运行 pip install pystray 后重试')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
        return
    
    # 创建托盘图标（蓝色圆形带"微"字）
    icon_size = 64
    img = PILImage.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, icon_size-4, icon_size-4], fill=(26, 115, 232, 255))
    try:
        font = ImageFont.truetype("msyh.ttc", 32)
    except:
        try:
            font = ImageFont.truetype("simhei.ttf", 32)
        except:
            font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "微", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (icon_size - tw) // 2 - bbox[0]
    ty = (icon_size - th) // 2 - bbox[1]
    draw.text((tx, ty), "微", fill=(255, 255, 255, 255), font=font)
    
    # 托盘菜单
    def open_ui(icon, item):
        webbrowser.open(f'http://localhost:{port}')
    
    def quit_app(icon, item):
        icon.stop()
        server.shutdown()
    
    menu = pystray.Menu(
        pystray.MenuItem('打开界面', open_ui, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f'访问地址：localhost:{port}', None, enabled=False),
        pystray.MenuItem('退出', quit_app),
    )
    
    icon = pystray.Icon('wfhelper', img, f'微信好友助手 - :{port}', menu)
    
    # 服务器在后台线程运行
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    # 第一次启动自动打开浏览器
    if OPEN_BROWSER:
        threading.Timer(2.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    
    # 运行托盘（阻塞主线程）
    icon.run()

if __name__ == '__main__':
    main()
