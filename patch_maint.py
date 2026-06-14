#!/usr/bin/env python3
"""维保日程提醒功能增强补丁"""
import re

with open('/app/data/所有对话/主对话/软件项目/微信好友助手/server/static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# ============================================================
# 1. 新增CSS样式（在 .maint-view-toggle button.active 后面追加）
# ============================================================
new_css = """
/* 维保记录 */
.maint-sub-tabs{display:flex;gap:4px;margin-bottom:12px;border-bottom:2px solid #eee;padding-bottom:6px}
.maint-sub-tab{padding:6px 16px;cursor:pointer;border-radius:6px 6px 0 0;font-size:13px;color:#666;border:1px solid transparent;border-bottom:none;background:transparent;transition:all .15s}
.maint-sub-tab:hover{color:#1a73e8;background:#f0f4ff}
.maint-sub-tab.active{color:#1a73e8;background:#e8f0fe;border:1px solid #d0d9f0;border-bottom:2px solid #fff;font-weight:600;margin-bottom:-2px}
.maint-record-item{background:#fff;border:1px solid #eee;border-radius:8px;padding:12px 14px;margin-bottom:8px;transition:box-shadow .15s}
.maint-record-item:hover{box-shadow:0 2px 8px rgba(0,0,0,.08)}
.maint-record-header{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.maint-record-date{font-weight:600;color:#1a73e8;font-size:13px}
.maint-record-person{font-size:12px;color:#888;background:#f0f4ff;padding:1px 8px;border-radius:10px}
.maint-record-contract{font-size:11px;color:#1a73e8;cursor:pointer}
.maint-record-contract:hover{text-decoration:underline}
.maint-record-content{font-size:12px;color:#555;line-height:1.6;margin:6px 0}
.maint-record-pdf{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;background:#fce8e6;color:#ea4335;border-radius:6px;font-size:11px;cursor:pointer;text-decoration:none}
.maint-record-pdf:hover{background:#f8d0cc}
.maint-record-actions{margin-top:6px;display:flex;gap:6px}
.maint-form{background:#f8f9ff;border-radius:8px;padding:14px;margin-bottom:14px;border:1px solid #d0d9f0}
.maint-form-row{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-bottom:8px}
.maint-form-row:last-child{margin-bottom:0}
.maint-form-row label{font-size:11px;color:#888;display:block;margin-bottom:2px}
.maint-form-row input,.maint-form-row select,.maint-form-row textarea{padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px}
.maint-form-row textarea{width:100%;min-height:60px;resize:vertical}
/* 注意事项表 */
.maint-notes-table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
.maint-notes-table th{background:#f0f4ff;padding:8px 10px;text-align:left;font-weight:600;color:#555;border:1px solid #d0d9f0}
.maint-notes-table td{padding:6px 10px;border:1px solid #eee;vertical-align:top}
.maint-notes-table tr:hover td{background:#f8f9ff}
.maint-notes-table .cat-cell{color:#1a73e8;font-weight:600;white-space:nowrap}
.maint-notes-table .freq-cell{white-space:nowrap;color:#888}
.maint-countdown{font-size:11px;font-weight:600;padding:2px 6px;border-radius:4px;margin-left:6px;white-space:nowrap}
.maint-countdown.cd-urgent{background:#fce8e6;color:#ea4335}
.maint-countdown.cd-warning{background:#fef7e0;color:#e37400}
.maint-countdown.cd-ok{background:#e6f4ea;color:#34a853}
"""

# Insert after .maint-view-toggle button.active{...}
anchor = ".maint-view-toggle button.active{background:#1a73e8;color:#fff;border-color:#1a73e8}"
html = html.replace(anchor, anchor + "\n" + new_css, 1)

# ============================================================
# 2. 新增数据键
# ============================================================
old_keys = "const DB_KEY='wfhelper_data',CFG_KEY='wfhelper_config',TPL_KEY='wfhelper_templates',CONTRACT_KEY='wfhelper_contracts',MAINT_KEY='wfhelper_maint_items';"
new_keys = "const DB_KEY='wfhelper_data',CFG_KEY='wfhelper_config',TPL_KEY='wfhelper_templates',CONTRACT_KEY='wfhelper_contracts',MAINT_KEY='wfhelper_maint_items',MAINT_RECORDS_KEY='wfhelper_maint_records',MAINT_NOTES_KEY='wfhelper_maint_notes';"
html = html.replace(old_keys, new_keys, 1)

# ============================================================
# 3. 新增 load/save 函数
# ============================================================
old_maint_funcs = "function loadMaintItems(){return apiGet(MAINT_KEY)}\nfunction saveMaintItems(d){apiPut(MAINT_KEY,d)}"
new_maint_funcs = """function loadMaintItems(){return apiGet(MAINT_KEY)}
function saveMaintItems(d){apiPut(MAINT_KEY,d)}
function loadMaintRecords(){return apiGet(MAINT_RECORDS_KEY)}
function saveMaintRecords(d){apiPut(MAINT_RECORDS_KEY,d)}
function loadMaintNotes(){return apiGet(MAINT_NOTES_KEY)}
function saveMaintNotes(d){apiPut(MAINT_NOTES_KEY,d)}"""
html = html.replace(old_maint_funcs, new_maint_funcs, 1)

# ============================================================
# 4. 新增全局变量
# ============================================================
old_vars = "let customers=[],config={dailyLimit:25,retryDays:3,myTitle:'悦动双成-展厅中控'},templates=[],contracts=[],maintItems=[],selectedId=null,selectedContractId=null;"
new_vars = "let customers=[],config={dailyLimit:25,retryDays:3,myTitle:'悦动双成-展厅中控'},templates=[],contracts=[],maintItems=[],maintRecords=[],maintNotes=[],selectedId=null,selectedContractId=null;"
html = html.replace(old_vars, new_vars, 1)

# ============================================================
# 5. 修改 initApp 加载新数据
# ============================================================
old_init = """  const [cData,cfgData,tplData,conData,mData]=await Promise.all([
      loadData(),loadConfig(),loadTemplates(),loadContracts(),loadMaintItems()
    ]);
    customers=cData||[];
    config=cfgData||{dailyLimit:25,retryDays:3,myTitle:'悦动双成-展厅中控'};
    templates=tplData||[];
    contracts=conData||[];
    maintItems=mData||[];"""
new_init = """  const [cData,cfgData,tplData,conData,mData,mrData,mnData]=await Promise.all([
      loadData(),loadConfig(),loadTemplates(),loadContracts(),loadMaintItems(),loadMaintRecords(),loadMaintNotes()
    ]);
    customers=cData||[];
    config=cfgData||{dailyLimit:25,retryDays:3,myTitle:'悦动双成-展厅中控'};
    templates=tplData||[];
    contracts=conData||[];
    maintItems=mData||[];
    maintRecords=mrData||[];
    maintNotes=mnData||[];"""
html = html.replace(old_init, new_init, 1)

# ============================================================
# 6. 修改 exportData 导出新数据
# ============================================================
old_export = "const data={customers:customers,config:config,templates:templates,contracts:contracts,maintItems:maintItems};"
new_export = "const data={customers:customers,config:config,templates:templates,contracts:contracts,maintItems:maintItems,maintRecords:maintRecords,maintNotes:maintNotes};"
html = html.replace(old_export, new_export, 1)

# ============================================================
# 7. 修改 importData 合并新数据（在 maintItems 合并后追加）
# ============================================================
old_import_maint = """          maintItems=mergedM;saveMaintItems(maintItems);"""
new_import_maint = """          maintItems=mergedM;saveMaintItems(maintItems);
        if(data.maintRecords&&data.maintRecords.length){
          const existRMap=new Map(maintRecords.map(r=>[r.id,r]));
          let mergedR=data.maintRecords.map(r=>existRMap.has(r.id)?existRMap.get(r.id):r);
          mergedR=mergedR.concat(maintRecords.filter(r=>!data.maintRecords.find(d=>d.id===r.id)));
          maintRecords=mergedR;saveMaintRecords(maintRecords);
        }
        if(data.maintNotes&&data.maintNotes.length){
          const existNMap=new Map(maintNotes.map(n=>[n.id,n]));
          let mergedN=data.maintNotes.map(n=>existNMap.has(n.id)?existNMap.get(n.id):n);
          mergedN=mergedN.concat(maintNotes.filter(n=>!data.maintNotes.find(d=>d.id===n.id)));
          maintNotes=mergedN;saveMaintNotes(maintNotes);
        }"""
html = html.replace(old_import_maint, new_import_maint, 1)

# ============================================================
# 8. 替换维保面板HTML - 改为子标签结构
# ============================================================
old_panel = '''<div class="panel" id="panel-maint">
  <div class="maint-toolbar">
    <span style="font-weight:600">📅 维保日程提醒</span>
    <button class="btn btn-primary btn-sm" onclick="toggleMaintAddForm()" style="margin-left:auto">+ 添加日程</button>
  </div>
  <div class="maint-content">
  <div id="maintAddForm" style="display:none;background:#f8f9ff;border-radius:8px;padding:14px;margin-bottom:14px;border:1px solid #d0d9f0">
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
      <div style="flex:1;min-width:120px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">标题 *</label><input type="text" id="maintAddTitle" placeholder="如：XX展厅年度维护" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"></div>
      <div style="min-width:100px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">类型</label><select id="maintAddType" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"><option value="custom">📌 自定义</option><option value="warranty">🛡️ 质保</option><option value="payment">💰 付款</option><option value="contract_end">📋 合同到期</option><option value="inspection">🔍 巡检</option><option value="renewal">🔄 续约</option></select></div>
      <div style="min-width:120px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">日期 *</label><input type="date" id="maintAddDate" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"></div>
      <div style="flex:1;min-width:120px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">关联合同</label><select id="maintAddContract" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"><option value="">无</option></select></div>
      <div style="flex:2;min-width:160px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">备注</label><input type="text" id="maintAddNote" placeholder="备注说明" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"></div>
      <div style="display:flex;gap:4px"><button class="btn btn-primary btn-sm" onclick="addMaintItem()">✅ 添加</button><button class="btn btn-sm" onclick="toggleMaintAddForm()">取消</button></div>
    </div>
  </div>
  <div class="maint-stats" id="maintStats"></div>
  <div class="maint-filters">
    <select id="maintFilterType" onchange="renderMaint()">
      <option value="all">全部类型</option>
      <option value="warranty">质保到期</option>
      <option value="payment">付款提醒</option>
      <option value="contract_end">合同到期</option>
      <option value="custom">📌 自定义</option>
      <option value="inspection">🔍 巡检</option>
      <option value="renewal">🔄 续约</option>
    </select>
    <select id="maintFilterStatus" onchange="renderMaint()">
      <option value="all">全部状态</option>
      <option value="urgent">🔴 逾期</option>
      <option value="warning">🟠 即将到期</option>
      <option value="info">🔵 未来</option>
      <option value="done">✅ 已完成</option>
    </select>
    <input type="text" id="maintSearch" placeholder="搜索..." oninput="renderMaint()" style="flex:1;max-width:200px">
    <div class="maint-view-toggle">
      <button id="maintViewTimeline" class="active" onclick="switchMaintView('timeline')">📋 时间线</button>
      <button id="maintViewCalendar" onclick="switchMaintView('calendar')">🗓️ 日历</button>
    </div>
  </div>
  <div id="maintTimelineView">
    <div class="maint-timeline" id="maintTimeline"></div>
  </div>
  <div id="maintCalendarView" style="display:none">
    <div class="maint-cal-nav">
      <button onclick="maintCalPrev()">◀</button>
      <span id="maintCalTitle">2026年6月</span>
      <button onclick="maintCalNext()">▶</button>
    </div>
    <div class="maint-calendar" id="maintCalendar"></div>
    <div id="maintCalDetail" style="margin-top:12px"></div>
  </div>
  </div>
</div>'''

new_panel = '''<div class="panel" id="panel-maint">
  <div class="maint-toolbar">
    <span style="font-weight:600">📅 维保日程提醒</span>
    <button class="btn btn-primary btn-sm" onclick="toggleMaintAddForm()" style="margin-left:auto">+ 添加日程</button>
  </div>
  <div class="maint-content">
  <!-- 子标签 -->
  <div class="maint-sub-tabs">
    <div class="maint-sub-tab active" onclick="switchMaintSubTab('schedule')" id="maintSubSchedule">📋 日程提醒</div>
    <div class="maint-sub-tab" onclick="switchMaintSubTab('records')" id="maintSubRecords">📝 维保记录</div>
    <div class="maint-sub-tab" onclick="switchMaintSubTab('notes')" id="maintSubNotes">⚠️ 注意事项</div>
  </div>

  <!-- === 日程提醒子面板 === -->
  <div id="maintSchedulePanel">
  <div id="maintAddForm" style="display:none;background:#f8f9ff;border-radius:8px;padding:14px;margin-bottom:14px;border:1px solid #d0d9f0">
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
      <div style="flex:1;min-width:120px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">标题 *</label><input type="text" id="maintAddTitle" placeholder="如：XX展厅年度维护" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"></div>
      <div style="min-width:100px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">类型</label><select id="maintAddType" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"><option value="custom">📌 自定义</option><option value="periodic_maint">🔧 定期维护</option><option value="warranty">🛡️ 质保到期</option><option value="payment">💰 付款</option><option value="contract_end">📋 合同到期</option><option value="inspection">🔍 巡检</option><option value="renewal">🔄 续约</option></select></div>
      <div style="min-width:120px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">日期 *</label><input type="date" id="maintAddDate" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"></div>
      <div style="flex:1;min-width:120px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">关联合同</label><select id="maintAddContract" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"><option value="">无</option></select></div>
      <div style="flex:2;min-width:160px"><label style="font-size:11px;color:#888;display:block;margin-bottom:2px">备注</label><input type="text" id="maintAddNote" placeholder="备注说明" style="width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px"></div>
      <div style="display:flex;gap:4px"><button class="btn btn-primary btn-sm" onclick="addMaintItem()">✅ 添加</button><button class="btn btn-sm" onclick="toggleMaintAddForm()">取消</button></div>
    </div>
  </div>
  <div class="maint-stats" id="maintStats"></div>
  <div class="maint-filters">
    <select id="maintFilterType" onchange="renderMaint()">
      <option value="all">全部类型</option>
      <option value="periodic_maint">🔧 定期维护</option>
      <option value="warranty">质保到期</option>
      <option value="payment">付款提醒</option>
      <option value="contract_end">合同到期</option>
      <option value="custom">📌 自定义</option>
      <option value="inspection">🔍 巡检</option>
      <option value="renewal">🔄 续约</option>
    </select>
    <select id="maintFilterStatus" onchange="renderMaint()">
      <option value="all">全部状态</option>
      <option value="urgent">🔴 逾期</option>
      <option value="warning">🟠 即将到期</option>
      <option value="info">🔵 未来</option>
      <option value="done">✅ 已完成</option>
    </select>
    <input type="text" id="maintSearch" placeholder="搜索..." oninput="renderMaint()" style="flex:1;max-width:200px">
    <div class="maint-view-toggle">
      <button id="maintViewTimeline" class="active" onclick="switchMaintView('timeline')">📋 时间线</button>
      <button id="maintViewCalendar" onclick="switchMaintView('calendar')">🗓️ 日历</button>
    </div>
  </div>
  <div id="maintTimelineView">
    <div class="maint-timeline" id="maintTimeline"></div>
  </div>
  <div id="maintCalendarView" style="display:none">
    <div class="maint-cal-nav">
      <button onclick="maintCalPrev()">◀</button>
      <span id="maintCalTitle">2026年6月</span>
      <button onclick="maintCalNext()">▶</button>
    </div>
    <div class="maint-calendar" id="maintCalendar"></div>
    <div id="maintCalDetail" style="margin-top:12px"></div>
  </div>
  </div>

  <!-- === 维保记录子面板 === -->
  <div id="maintRecordsPanel" style="display:none">
  <div style="display:flex;gap:8px;margin-bottom:14px;align-items:center">
    <button class="btn btn-primary btn-sm" onclick="toggleMaintRecordForm()">+ 添加维保记录</button>
    <select id="maintRecordFilterContract" onchange="renderMaintRecords()" style="padding:5px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px">
      <option value="all">全部合同</option>
    </select>
    <input type="text" id="maintRecordSearch" placeholder="搜索记录..." oninput="renderMaintRecords()" style="flex:1;max-width:200px;padding:5px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px">
  </div>
  <div id="maintRecordForm" style="display:none" class="maint-form">
    <div class="maint-form-row">
      <div style="flex:1;min-width:120px"><label>维保日期 *</label><input type="date" id="mrDate" style="width:100%"></div>
      <div style="min-width:100px"><label>维保人员</label><input type="text" id="mrPerson" placeholder="如：张三" style="width:100%"></div>
      <div style="flex:1;min-width:150px"><label>关联合同</label><select id="mrContract" style="width:100%"><option value="">无</option></select></div>
    </div>
    <div class="maint-form-row">
      <div style="flex:1"><label>维保内容 *</label><textarea id="mrContent" placeholder="详细描述本次维保的工作内容、更换的设备等"></textarea></div>
    </div>
    <div class="maint-form-row">
      <div style="flex:1"><label>上传PDF报告</label><input type="file" id="mrPdf" accept=".pdf" style="font-size:12px"></div>
    </div>
    <div class="maint-form-row">
      <button class="btn btn-primary btn-sm" onclick="saveMaintRecord()">💾 保存记录</button>
      <button class="btn btn-sm" onclick="toggleMaintRecordForm()">取消</button>
    </div>
  </div>
  <div id="maintRecordsList"></div>
  </div>

  <!-- === 注意事项子面板 === -->
  <div id="maintNotesPanel" style="display:none">
  <div style="display:flex;gap:8px;margin-bottom:14px;align-items:center">
    <button class="btn btn-primary btn-sm" onclick="toggleMaintNoteForm()">+ 添加注意事项</button>
    <span style="font-size:12px;color:#888;margin-left:auto">维保前请对照检查，确保不遗漏</span>
  </div>
  <div id="maintNoteForm" style="display:none" class="maint-form">
    <div class="maint-form-row">
      <div style="min-width:100px"><label>分类</label><input type="text" id="mnCategory" placeholder="如：投影设备" style="width:100%"></div>
      <div style="flex:1"><label>检查项目 *</label><input type="text" id="mnItem" placeholder="如：检查灯泡寿命" style="width:100%"></div>
      <div style="min-width:80px"><label>频率</label><input type="text" id="mnFreq" placeholder="如：每3个月" style="width:100%"></div>
      <div style="flex:2"><label>注意事项</label><input type="text" id="mnNote" placeholder="如：灯泡超2000h需更换" style="width:100%"></div>
      <div style="display:flex;gap:4px"><button class="btn btn-primary btn-sm" onclick="addMaintNote()">✅ 添加</button><button class="btn btn-sm" onclick="toggleMaintNoteForm()">取消</button></div>
    </div>
  </div>
  <div id="maintNotesTable"></div>
  </div>

  </div>
</div>'''

html = html.replace(old_panel, new_panel, 1)

# ============================================================
# 9. 增强 getMaintEvents - 添加定期维护自动生成 + 质保到期倒计时
# ============================================================
old_get_events = """function getMaintEvents(){
  const now=new Date().toISOString().slice(0,10);
  const wk7=new Date(Date.now()+7*864e5).toISOString().slice(0,10);
  const mo30=new Date(Date.now()+30*864e5).toISOString().slice(0,10);
  const events=[];
  contracts.forEach(c=>{
    // 质保到期
    if(c.warrantyEnd&&c.warrantyAmount&&!c.warrantyPaidDate){
      let severity='info';
      if(c.warrantyEnd<now) severity='urgent';
      else if(c.warrantyEnd<=mo30) severity='warning';
      events.push({type:'warranty',date:c.warrantyEnd,severity,contractId:c.id,
        title:`质保到期 - ${c.name||'未命名'}`,
        desc:`质保金 ¥${(c.warrantyAmount||0).toLocaleString()}，质保至 ${c.warrantyEnd}`});
    }
    // 付款提醒
    if(c.payments){
      c.payments.forEach((p,i)=>{
        if(p.paidDate||!p.date)return;
        let severity='info';
        if(p.date<now) severity='urgent';
        else if(p.date<=wk7) severity='warning';
        events.push({type:'payment',date:p.date,severity,contractId:c.id,
          title:`${p.name||'付款'+(i+1)} - ${c.name||'未命名'}`,
          desc:`应收 ¥${(p.amount||0).toLocaleString()}，到期日 ${p.date}`});
      });
    }
    // 合同到期
    if(c.endDate){
      let severity='info';
      if(c.endDate<now) severity='urgent';
      else if(c.endDate<=mo30) severity='warning';
      events.push({type:'contract_end',date:c.endDate,severity,contractId:c.id,
        title:`合同到期 - ${c.name||'未命名'}`,
        desc:`合同期 ${c.startDate||'?'} ~ ${c.endDate}，金额 ¥${(c.amount||0).toLocaleString()}`});
    }
  });
  // 自定义维保日程
  maintItems.forEach(m=>{
    let severity=m.done?'done':'info';
    if(!m.done){
      if(m.date<now) severity='urgent';
      else if(m.date<=mo30) severity='warning';
    }
    events.push({type:m.type,date:m.date,severity,contractId:m.contractId||'',itemId:m.id,
      title:m.title,desc:m.note||'',done:!!m.done});
  });
  events.sort((a,b)=>a.date.localeCompare(b.date));
  return events;
}"""

new_get_events = """function getMaintEvents(){
  const now=new Date().toISOString().slice(0,10);
  const nowTs=Date.now();
  const wk7=new Date(nowTs+7*864e5).toISOString().slice(0,10);
  const mo30=new Date(nowTs+30*864e5).toISOString().slice(0,10);
  const events=[];
  // 计算倒计时文字
  function countdown(targetDate){
    const diff=Math.ceil((new Date(targetDate+'T00:00:00')-new Date(now+'T00:00:00'))/864e5);
    if(diff<0) return {text:`已逾期${Math.abs(diff)}天`,cls:'cd-urgent'};
    if(diff===0) return {text:'今天到期',cls:'cd-urgent'};
    if(diff<=7) return {text:`${diff}天后到期`,cls:'cd-warning'};
    if(diff<=30) return {text:`${diff}天后到期`,cls:'cd-warning'};
    return {text:`${diff}天后到期`,cls:'cd-ok'};
  }
  contracts.forEach(c=>{
    // 质保期内定期维护提醒
    if(c.warrantyStart&&c.warrantyEnd){
      const ws=new Date(c.warrantyStart+'T00:00:00');
      const we=new Date(c.warrantyEnd+'T00:00:00');
      const intervalMonths=config.maintInterval||3; // 默认每3个月
      let d=new Date(ws);
      d.setMonth(d.getMonth()+intervalMonths);
      while(d<=we){
        const ds=d.toISOString().slice(0,10);
        // 检查是否已有对应日程（避免重复生成）
        const exists=maintItems.some(m=>m.contractId===c.id&&m.type==='periodic_maint'&&m.date===ds);
        if(!exists&&ds>=now){
          let severity='info';
          if(ds<wk7) severity='warning';
          events.push({type:'periodic_maint',date:ds,severity,contractId:c.id,autoGenerated:true,
            title:`🔧 定期维护 - ${c.name||'未命名'}`,
            desc:`质保期内定期维护（每${intervalMonths}个月），质保期 ${c.warrantyStart} ~ ${c.warrantyEnd}`});
        }
        d=new Date(d);
        d.setMonth(d.getMonth()+intervalMonths);
      }
    }
    // 质保到期（增强：显示倒计时）
    if(c.warrantyEnd&&c.warrantyAmount&&!c.warrantyPaidDate){
      let severity='info';
      if(c.warrantyEnd<now) severity='urgent';
      else if(c.warrantyEnd<=mo30) severity='warning';
      const cd=countdown(c.warrantyEnd);
      events.push({type:'warranty',date:c.warrantyEnd,severity,contractId:c.id,
        title:`质保到期 - ${c.name||'未命名'}`,
        desc:`质保金 ¥${(c.warrantyAmount||0).toLocaleString()}，质保至 ${c.warrantyEnd} <span class="maint-countdown ${cd.cls}">${cd.text}</span>`});
    }
    // 质保到期时间提醒（即使无质保金也要提醒）
    if(c.warrantyEnd&&!c.warrantyAmount){
      const cd=countdown(c.warrantyEnd);
      let severity='info';
      if(c.warrantyEnd<now) severity='urgent';
      else if(c.warrantyEnd<=mo30) severity='warning';
      if(severity!=='info'||c.warrantyEnd<=mo30){ // 只提醒即将到期或已逾期的
        events.push({type:'warranty',date:c.warrantyEnd,severity,contractId:c.id,
          title:`质保期到期 - ${c.name||'未命名'}`,
          desc:`质保期 ${c.warrantyStart||'?'} ~ ${c.warrantyEnd} <span class="maint-countdown ${cd.cls}">${cd.text}</span>`});
      }
    }
    // 付款提醒
    if(c.payments){
      c.payments.forEach((p,i)=>{
        if(p.paidDate||!p.date)return;
        let severity='info';
        if(p.date<now) severity='urgent';
        else if(p.date<=wk7) severity='warning';
        events.push({type:'payment',date:p.date,severity,contractId:c.id,
          title:`${p.name||'付款'+(i+1)} - ${c.name||'未命名'}`,
          desc:`应收 ¥${(p.amount||0).toLocaleString()}，到期日 ${p.date}`});
      });
    }
    // 合同到期
    if(c.endDate){
      let severity='info';
      if(c.endDate<now) severity='urgent';
      else if(c.endDate<=mo30) severity='warning';
      const cd=countdown(c.endDate);
      events.push({type:'contract_end',date:c.endDate,severity,contractId:c.id,
        title:`合同到期 - ${c.name||'未命名'}`,
        desc:`合同期 ${c.startDate||'?'} ~ ${c.endDate}，金额 ¥${(c.amount||0).toLocaleString()} <span class="maint-countdown ${cd.cls}">${cd.text}</span>`});
    }
  });
  // 自定义维保日程
  maintItems.forEach(m=>{
    let severity=m.done?'done':'info';
    if(!m.done){
      if(m.date<now) severity='urgent';
      else if(m.date<=mo30) severity='warning';
    }
    events.push({type:m.type,date:m.date,severity,contractId:m.contractId||'',itemId:m.id,
      title:m.title,desc:m.note||'',done:!!m.done});
  });
  events.sort((a,b)=>a.date.localeCompare(b.date));
  return events;
}"""

html = html.replace(old_get_events, new_get_events, 1)

# ============================================================
# 10. 增强时间线渲染 - 支持 periodic_maint 类型 + 倒计时HTML
# ============================================================
# 更新 typeIcon 添加 periodic_maint
html = html.replace(
    "const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄'};",
    "const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄',periodic_maint:'🔧'};",
    1  # 只替换第一个（时间线渲染里的）
)

# 第二个 typeIcon（日历详情里的）
# 需要找到第二个出现位置
remaining = html[html.index("const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄'};") + 10:]
if "const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄'};" in remaining:
    # 替换第二个
    second_idx = html.index("const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄'};", 
                            html.index("const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄'};") + 10)
    html = html[:second_idx] + "const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄',periodic_maint:'🔧'};" + html[second_idx + len("const typeIcon={warranty:'🛡️',payment:'💰',contract_end:'📋',custom:'📌',inspection:'🔍',renewal:'🔄'};"):]

# 修改 desc 渲染 - 支持 HTML（倒计时标签）
# 在时间线渲染中，desc 现在包含 HTML，需要用 innerHTML 渲染
# 但当前代码用的是模板字符串直接嵌入，所以 HTML 会自动渲染
# 检查是否有转义问题 - 没有，模板字符串中的 HTML 会被浏览器解析
# 所以只需要确保 desc 渲染时不做转义即可

# ============================================================
# 11. 修改 completeMaintItem - 完成时弹出记录表单
# ============================================================
old_complete = """function completeMaintItem(id){
  const m=maintItems.find(x=>x.id===id);
  if(m){m.done=true;saveMaintItems(maintItems);renderMaint();showToast('已标记完成','success')}
}"""
new_complete = """function completeMaintItem(id){
  const m=maintItems.find(x=>x.id===id);
  if(!m)return;
  // 弹出快速记录表单
  const contractName=m.contractId?(contracts.find(c=>c.id===m.contractId)||{}).name||'':'';
  const person=prompt('维保人员姓名：');
  if(person===null)return; // 取消
  const content=prompt('维保内容简述：')||m.title;
  // 标记完成
  m.done=true;
  m.completedAt=new Date().toISOString();
  saveMaintItems(maintItems);
  // 自动创建维保记录
  const record={
    id:Date.now().toString(36)+Math.random().toString(36).slice(2,6),
    date:todayStr(),
    person:person||'未填写',
    content:content,
    contractId:m.contractId||'',
    maintItemId:id,
    pdfFileId:'',
    createdAt:new Date().toISOString()
  };
  maintRecords.push(record);
  saveMaintRecords(maintRecords);
  renderMaint();
  showToast('已完成并记录维保','success');
}"""
html = html.replace(old_complete, new_complete, 1)

# ============================================================
# 12. 修改 renderMaintStats 添加定期维护统计
# ============================================================
old_stats = """  const warrantyCount=events.filter(e=>e.type==='warranty').length;
  document.getElementById('maintStats').innerHTML=`
    <div class="maint-stat-card urgent"><div class="num">${urgentCount}</div><div class="label">🔴 逾期</div></div>
    <div class="maint-stat-card warning"><div class="num">${warningCount}</div><div class="label">🟠 即将到期</div></div>
    <div class="maint-stat-card"><div class="num">${totalCount-urgentCount-warningCount-doneCount}</div><div class="label">🔵 未来</div></div>
    <div class="maint-stat-card ok"><div class="num">${doneCount}</div><div class="label">✅ 已完成</div></div>
    <div class="maint-stat-card"><div class="num">${warrantyCount}</div><div class="label">🛡️ 质保提醒</div></div>
  `;"""
new_stats = """  const warrantyCount=events.filter(e=>e.type==='warranty').length;
  const periodicCount=events.filter(e=>e.type==='periodic_maint').length;
  const recordCount=maintRecords.length;
  document.getElementById('maintStats').innerHTML=`
    <div class="maint-stat-card urgent"><div class="num">${urgentCount}</div><div class="label">🔴 逾期</div></div>
    <div class="maint-stat-card warning"><div class="num">${warningCount}</div><div class="label">🟠 即将到期</div></div>
    <div class="maint-stat-card"><div class="num">${totalCount-urgentCount-warningCount-doneCount}</div><div class="label">🔵 未来</div></div>
    <div class="maint-stat-card ok"><div class="num">${doneCount}</div><div class="label">✅ 已完成</div></div>
    <div class="maint-stat-card"><div class="num">${periodicCount}</div><div class="label">🔧 定期维护</div></div>
    <div class="maint-stat-card"><div class="num">${warrantyCount}</div><div class="label">🛡️ 质保提醒</div></div>
    <div class="maint-stat-card"><div class="num">${recordCount}</div><div class="label">📝 维保记录</div></div>
  `;"""
html = html.replace(old_stats, new_stats, 1)

# ============================================================
# 13. 在 deleteMaintItem 后面添加新的 JS 函数
# ============================================================
new_functions = """

// === 维保子标签切换 ===
function switchMaintSubTab(tab){
  document.querySelectorAll('.maint-sub-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('maintSchedulePanel').style.display='none';
  document.getElementById('maintRecordsPanel').style.display='none';
  document.getElementById('maintNotesPanel').style.display='none';
  if(tab==='schedule'){
    document.getElementById('maintSubSchedule').classList.add('active');
    document.getElementById('maintSchedulePanel').style.display='';
  }else if(tab==='records'){
    document.getElementById('maintSubRecords').classList.add('active');
    document.getElementById('maintRecordsPanel').style.display='';
    renderMaintRecords();
  }else if(tab==='notes'){
    document.getElementById('maintSubNotes').classList.add('active');
    document.getElementById('maintNotesPanel').style.display='';
    renderMaintNotes();
  }
}

// === 维保记录管理 ===
function toggleMaintRecordForm(){
  const f=document.getElementById('maintRecordForm');
  f.style.display=f.style.display==='none'?'':'none';
  if(f.style.display!=='none'){
    document.getElementById('mrDate').value=todayStr();
    document.getElementById('mrPerson').value='';
    document.getElementById('mrContent').value='';
    document.getElementById('mrPdf').value='';
    // 填充合同下拉
    const sel=document.getElementById('mrContract');
    sel.innerHTML='<option value="">无</option>'+contracts.map(c=>`<option value="${c.id}">${c.name||'未命名'}</option>`).join('');
    document.getElementById('mrDate').focus();
  }
}

async function saveMaintRecord(){
  const date=document.getElementById('mrDate').value;
  const person=document.getElementById('mrPerson').value.trim();
  const content=document.getElementById('mrContent').value.trim();
  const contractId=document.getElementById('mrContract').value;
  const pdfInput=document.getElementById('mrPdf');
  if(!date){showToast('请选择维保日期','error');return}
  if(!content){showToast('请填写维保内容','error');return}
  let pdfFileId='';
  // 上传PDF
  if(pdfInput.files&&pdfInput.files[0]){
    try{
      const fd=new FormData();fd.append('file',pdfInput.files[0]);
      const r=await fetch('/api/files/upload',{method:'POST',body:fd});
      const data=await r.json();
      if(data.id) pdfFileId=data.id;
    }catch(e){console.error('PDF上传失败:',e)}
  }
  const record={
    id:Date.now().toString(36)+Math.random().toString(36).slice(2,6),
    date,person:person||'未填写',content,contractId,pdfFileId,
    maintItemId:'',
    createdAt:new Date().toISOString()
  };
  maintRecords.push(record);
  saveMaintRecords(maintRecords);
  toggleMaintRecordForm();
  renderMaintRecords();
  renderMaint(); // 刷新统计
  showToast('维保记录已保存','success');
}

function deleteMaintRecord(id){
  if(!confirm('确定删除此维保记录？'))return;
  maintRecords=maintRecords.filter(r=>r.id!==id);
  saveMaintRecords(maintRecords);
  renderMaintRecords();
  renderMaint();
  showToast('记录已删除','success');
}

function renderMaintRecords(){
  const filterContract=document.getElementById('maintRecordFilterContract').value;
  const search=document.getElementById('maintRecordSearch').value.trim().toLowerCase();
  // 填充合同筛选下拉
  const sel=document.getElementById('maintRecordFilterContract');
  const curVal=sel.value;
  sel.innerHTML='<option value="all">全部合同</option>'+contracts.map(c=>`<option value="${c.id}">${c.name||'未命名'}</option>`).join('');
  sel.value=curVal||'all';
  let records=[...maintRecords].sort((a,b)=>b.date.localeCompare(a.date));
  if(filterContract!=='all') records=records.filter(r=>r.contractId===filterContract);
  if(search) records=records.filter(r=>r.content.toLowerCase().includes(search)||r.person.toLowerCase().includes(search)||(r.date||'').includes(search));
  const el=document.getElementById('maintRecordsList');
  if(!records.length){
    el.innerHTML='<div class="maint-empty">📝 暂无维保记录，点击上方按钮添加</div>';
    return;
  }
  el.innerHTML=records.map(r=>{
    const contract=r.contractId?contracts.find(c=>c.id===r.contractId):null;
    const contractLink=contract?`<span class="maint-record-contract" onclick="goToContract('${r.contractId}')">📄 ${contract.name||'未命名'}</span>`:'';
    const pdfLink=r.pdfFileId?`<a class="maint-record-pdf" href="/api/files/${r.pdfFileId}" target="_blank">📎 查看PDF报告</a>`:'';
    return `<div class="maint-record-item">
      <div class="maint-record-header">
        <span class="maint-record-date">${r.date}</span>
        <span class="maint-record-person">👤 ${r.person}</span>
        ${contractLink}
        <span style="margin-left:auto;font-size:11px">
          <a href="javascript:void(0)" onclick="deleteMaintRecord('${r.id}')" style="color:#ea4335">删除</a>
        </span>
      </div>
      <div class="maint-record-content">${r.content.replace(/\\n/g,'<br>')}</div>
      <div>${pdfLink}</div>
    </div>`;
  }).join('');
}

// === 维保注意事项管理 ===
const DEFAULT_MAINT_NOTES=[
  {id:'dn1',category:'投影设备',item:'检查投影机灯泡使用时间',frequency:'每3个月',note:'灯泡超过2000小时需更换，备好备品'},
  {id:'dn2',category:'投影设备',item:'清洁投影机滤网和镜头',frequency:'每3个月',note:'用气吹清理灰尘，镜头用专用清洁布'},
  {id:'dn3',category:'投影设备',item:'检查投影机信号线连接',frequency:'每6个月',note:'HDMI/VGA线材易松动，重新插拔确认'},
  {id:'dn4',category:'LED屏',item:'检查LED模组显示效果',frequency:'每3个月',note:'观察是否有坏点、色差、亮度不均'},
  {id:'dn5',category:'LED屏',item:'检查LED控制卡和发送卡',frequency:'每6个月',note:'确认通讯正常，固件版本是否需更新'},
  {id:'dn6',category:'LED屏',item:'清洁LED屏幕表面',frequency:'每3个月',note:'用柔软干布擦拭，禁用有机溶剂'},
  {id:'dn7',category:'音响系统',item:'测试各声道音箱输出',frequency:'每3个月',note:'逐一检查是否有杂音、失真、无声'},
  {id:'dn8',category:'音响系统',item:'检查功放和调音台',frequency:'每6个月',note:'确认各通道正常，旋钮无松动'},
  {id:'dn9',category:'音响系统',item:'检查音频线材和接头',frequency:'每6个月',note:'6.35mm/XLR接口易氧化，必要时清洁'},
  {id:'dn10',category:'中控系统',item:'检查中控主机运行状态',frequency:'每3个月',note:'CPU/内存使用率、服务进程是否正常'},
  {id:'dn11',category:'中控系统',item:'测试各设备控制指令',frequency:'每3个月',note:'逐一测试开关机、信号切换、音量调节'},
  {id:'dn12',category:'中控系统',item:'检查中控界面触控响应',frequency:'每6个月',note:'触控屏校准、按键响应速度'},
  {id:'dn13',category:'拼接屏',item:'检查55寸拼接屏显示',frequency:'每3个月',note:'观察拼缝是否有亮线，色彩一致性'},
  {id:'dn14',category:'拼接屏',item:'检查拼接处理器',frequency:'每6个月',note:'信号源切换测试，分辨率和刷新率确认'},
  {id:'dn15',category:'网络设备',item:'检查交换机和路由器',frequency:'每3个月',note:'端口指示灯、丢包率、固件版本'},
  {id:'dn16',category:'网络设备',item:'检查网络线缆和接口',frequency:'每6个月',note:'网线水晶头是否氧化松动'},
  {id:'dn17',category:'服务器',item:'检查服务器硬件状态',frequency:'每3个月',note:'硬盘SMART、风扇转速、温度'},
  {id:'dn18',category:'服务器',item:'备份数据和配置',frequency:'每3个月',note:'数据库备份、中控配置备份、系统镜像'},
  {id:'dn19',category:'综合',item:'检查UPS电源和供电',frequency:'每3个月',note:'电池容量、市电/旁路切换测试'},
  {id:'dn20',category:'综合',item:'检查机房温湿度环境',frequency:'每3个月',note:'空调运行正常，温度20-25°C，湿度40-60%'},
  {id:'dn21',category:'综合',item:'整理线缆和标签',frequency:'每6个月',note:'理线、更新标签、清理废弃线材'},
  {id:'dn22',category:'综合',item:'拍摄现场照片存档',frequency:'每次维保',note:'拍摄设备状态、维护前后对比照'}
];

function toggleMaintNoteForm(){
  const f=document.getElementById('maintNoteForm');
  f.style.display=f.style.display==='none'?'':'none';
  if(f.style.display!=='none'){
    document.getElementById('mnCategory').value='';
    document.getElementById('mnItem').value='';
    document.getElementById('mnFreq').value='';
    document.getElementById('mnNote').value='';
    document.getElementById('mnCategory').focus();
  }
}

function addMaintNote(){
  const category=document.getElementById('mnCategory').value.trim();
  const item=document.getElementById('mnItem').value.trim();
  const frequency=document.getElementById('mnFreq').value.trim();
  const note=document.getElementById('mnNote').value.trim();
  if(!item){showToast('请填写检查项目','error');return}
  const n={id:Date.now().toString(36)+Math.random().toString(36).slice(2,6),category:category||'其他',item,frequency:frequency||'按需',note};
  maintNotes.push(n);
  saveMaintNotes(maintNotes);
  toggleMaintNoteForm();
  renderMaintNotes();
  showToast('注意事项已添加','success');
}

function deleteMaintNote(id){
  if(!confirm('确定删除此注意事项？'))return;
  maintNotes=maintNotes.filter(n=>n.id!==id);
  saveMaintNotes(maintNotes);
  renderMaintNotes();
  showToast('已删除','success');
}

function resetMaintNotesToDefault(){
  if(!confirm('确定恢复默认注意事项？自定义内容将被覆盖。'))return;
  maintNotes=JSON.parse(JSON.stringify(DEFAULT_MAINT_NOTES));
  saveMaintNotes(maintNotes);
  renderMaintNotes();
  showToast('已恢复默认','success');
}

function renderMaintNotes(){
  // 如果首次使用，加载默认
  if(!maintNotes.length){
    maintNotes=JSON.parse(JSON.stringify(DEFAULT_MAINT_NOTES));
    saveMaintNotes(maintNotes);
  }
  // 按分类分组
  const groups={};
  maintNotes.forEach(n=>{
    const cat=n.category||'其他';
    if(!groups[cat]) groups[cat]=[];
    groups[cat].push(n);
  });
  const el=document.getElementById('maintNotesTable');
  let html='<table class="maint-notes-table"><thead><tr><th style="width:90px">分类</th><th>检查项目</th><th style="width:80px">频率</th><th>注意事项</th><th style="width:50px">操作</th></tr></thead><tbody>';
  Object.keys(groups).forEach(cat=>{
    groups[cat].forEach((n,i)=>{
      html+=`<tr>${i===0?`<td class="cat-cell" rowspan="${groups[cat].length}">${cat}</td>`:''}<td>${n.item}</td><td class="freq-cell">${n.frequency}</td><td>${n.note||'-'}</td><td><a href="javascript:void(0)" onclick="deleteMaintNote('${n.id}')" style="color:#ea4335;font-size:11px">删除</a></td></tr>`;
    });
  });
  html+='</tbody></table>';
  html+=`<div style="margin-top:8px;text-align:right"><button class="btn btn-sm" onclick="resetMaintNotesToDefault()" style="color:#888">🔄 恢复默认</button></div>`;
  el.innerHTML=html;
}

// === 合同保存时自动生成定期维护日程 ===
function autoGeneratePeriodicMaint(contract){
  if(!contract.warrantyStart||!contract.warrantyEnd)return;
  const intervalMonths=config.maintInterval||3;
  const ws=new Date(contract.warrantyStart+'T00:00:00');
  const we=new Date(contract.warrantyEnd+'T00:00:00');
  const now=new Date().toISOString().slice(0,10);
  let d=new Date(ws);
  d.setMonth(d.getMonth()+intervalMonths);
  let added=0;
  while(d<=we){
    const ds=d.toISOString().slice(0,10);
    // 只在未来日期且不重复时创建
    if(ds>=now&&!maintItems.some(m=>m.contractId===contract.id&&m.type==='periodic_maint'&&m.date===ds)){
      const item={
        id:Date.now().toString(36)+Math.random().toString(36).slice(2,6)+added,
        title:`定期维护 - ${contract.name||'未命名'}`,
        type:'periodic_maint',
        date:ds,
        contractId:contract.id,
        note:`质保期内定期维护（每${intervalMonths}个月）`,
        done:false,
        autoGenerated:true,
        createdAt:new Date().toISOString()
      };
      maintItems.push(item);
      added++;
    }
    d=new Date(d);
    d.setMonth(d.getMonth()+intervalMonths);
  }
  if(added>0){
    saveMaintItems(maintItems);
  }
  return added;
}
"""

# 在 deleteMaintItem 后面插入
old_delete_maint = """function deleteMaintItem(id){
  maintItems=maintItems.filter(x=>x.id!==id);
  saveMaintItems(maintItems);
  renderMaint();
  showToast('日程已删除','success');
}"""
new_delete_maint = """function deleteMaintItem(id){
  maintItems=maintItems.filter(x=>x.id!==id);
  saveMaintItems(maintItems);
  renderMaint();
  showToast('日程已删除','success');
}""" + new_functions
html = html.replace(old_delete_maint, new_delete_maint, 1)

# ============================================================
# 14. 在合同保存后调用自动生成定期维护
# ============================================================
old_save_contract = """function saveContract(){
  if(!selectedContractId){showToast('请先选择合同','error');return}
  const c=contracts.find(x=>x.id===selectedContractId);if(!c)return;
  const d=collectContractData();Object.assign(c,d);c.updatedAt=new Date().toISOString();
  saveContractsData(contracts);renderContractList();renderContractDetail(c);renderContractAlerts();showToast('合同已保存','success');
}"""
new_save_contract = """function saveContract(){
  if(!selectedContractId){showToast('请先选择合同','error');return}
  const c=contracts.find(x=>x.id===selectedContractId);if(!c)return;
  const d=collectContractData();Object.assign(c,d);c.updatedAt=new Date().toISOString();
  saveContractsData(contracts);
  // 自动生成定期维护日程
  const added=autoGeneratePeriodicMaint(c);
  renderContractList();renderContractDetail(c);renderContractAlerts();
  if(added>0) showToast(`合同已保存，自动生成${added}条定期维护日程`,'success');
  else showToast('合同已保存','success');
}"""
html = html.replace(old_save_contract, new_save_contract, 1)

# ============================================================
# 15. 在设置面板添加维护间隔配置
# ============================================================
# 找到设置面板中的保存路径配置后面，添加维护间隔配置
old_stamp_dir = """  <div class="form-row"><label>盖章保存路径</label><input type="text" id="cfgStampSaveDir" placeholder="如：D:/盖章文件" style="flex:1"><button class="btn btn-sm" onclick="document.getElementById('cfgStampSaveDir').value=config.stampSaveDir||''">重置</button></div>"""
new_stamp_dir = """  <div class="form-row"><label>盖章保存路径</label><input type="text" id="cfgStampSaveDir" placeholder="如：D:/盖章文件" style="flex:1"><button class="btn btn-sm" onclick="document.getElementById('cfgStampSaveDir').value=config.stampSaveDir||''">重置</button></div>
  <div class="form-row"><label>定期维护间隔（月）</label><input type="number" id="cfgMaintInterval" min="1" max="12" value="3" style="width:60px"><span style="font-size:11px;color:#888;margin-left:4px">质保期内自动生成定期维护提醒的间隔</span></div>"""
html = html.replace(old_stamp_dir, new_stamp_dir, 1)

# 保存配置时也要读取 maintInterval
old_save_config = """function saveConfig(){
  config.dailyLimit=parseInt(document.getElementById('cfgLimit').value)||25;
  config.retryDays=parseInt(document.getElementById('cfgRetry').value)||3;
  config.myTitle=document.getElementById('cfgTitle').value.trim()||'悦动双成-展厅中控';
  config.stampSaveDir=document.getElementById('cfgStampSaveDir').value.trim();
  // 同步到盖章面板
  document.getElementById('espSaveDir').value=config.stampSaveDir||'';
  saveConfigToStorage(config);renderAll();showToast('设置已保存','success');
}"""
new_save_config = """function saveConfig(){
  config.dailyLimit=parseInt(document.getElementById('cfgLimit').value)||25;
  config.retryDays=parseInt(document.getElementById('cfgRetry').value)||3;
  config.myTitle=document.getElementById('cfgTitle').value.trim()||'悦动双成-展厅中控';
  config.stampSaveDir=document.getElementById('cfgStampSaveDir').value.trim();
  config.maintInterval=parseInt(document.getElementById('cfgMaintInterval').value)||3;
  // 同步到盖章面板
  document.getElementById('espSaveDir').value=config.stampSaveDir||'';
  saveConfigToStorage(config);renderAll();showToast('设置已保存','success');
}"""
html = html.replace(old_save_config, new_save_config, 1)

# 初始化时也要读取 maintInterval
old_init_cfg = """  document.getElementById('cfgStampSaveDir').value=config.stampSaveDir||'';
  document.getElementById('espSaveDir').value=config.stampSaveDir||'';"""
new_init_cfg = """  document.getElementById('cfgStampSaveDir').value=config.stampSaveDir||'';
  document.getElementById('espSaveDir').value=config.stampSaveDir||'';
  document.getElementById('cfgMaintInterval').value=config.maintInterval||3;"""
html = html.replace(old_init_cfg, new_init_cfg, 1)

# ============================================================
# 写入文件
# ============================================================
with open('/app/data/所有对话/主对话/软件项目/微信好友助手/server/static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("✅ 补丁应用成功！")

# 验证关键标记
checks = [
    ('MAINT_RECORDS_KEY', 'MAINT_RECORDS_KEY' in html),
    ('MAINT_NOTES_KEY', 'MAINT_NOTES_KEY' in html),
    ('maintRecords=[]', 'maintRecords=[]' in html),
    ('maintNotes=[]', 'maintNotes=[]' in html),
    ('loadMaintRecords', 'loadMaintRecords' in html),
    ('saveMaintRecords', 'saveMaintRecords' in html),
    ('loadMaintNotes', 'loadMaintNotes' in html),
    ('saveMaintNotes', 'saveMaintNotes' in html),
    ('periodic_maint', 'periodic_maint' in html),
    ('countdown', html.count('function countdown') >= 1),
    ('switchMaintSubTab', 'switchMaintSubTab' in html),
    ('renderMaintRecords', 'renderMaintRecords' in html),
    ('renderMaintNotes', 'renderMaintNotes' in html),
    ('autoGeneratePeriodicMaint', 'autoGeneratePeriodicMaint' in html),
    ('maintSchedulePanel', 'maintSchedulePanel' in html),
    ('maintRecordsPanel', 'maintRecordsPanel' in html),
    ('maintNotesPanel', 'maintNotesPanel' in html),
    ('DEFAULT_MAINT_NOTES', 'DEFAULT_MAINT_NOTES' in html),
    ('cfgMaintInterval', 'cfgMaintInterval' in html),
]
for name, ok in checks:
    print(f"  {'✅' if ok else '❌'} {name}")
