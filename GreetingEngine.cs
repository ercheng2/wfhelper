using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;

namespace WeChatFriendHelper
{
    public static class GreetingEngine
    {
        /// <summary>
        /// 根据客户信息和模板生成添加备注和打招呼话术
        /// </summary>
        public static (string remark, string greeting) Generate(Customer customer, DailyConfig config, List<GreetingTemplate> templates)
        {
            // 优先匹配：来源+行业 > 来源通用 > 通用
            GreetingTemplate? matched = null;

            // 1. 精确匹配：来源类型+行业
            foreach (var t in templates)
            {
                if (string.Equals(t.SourceType, customer.Source, StringComparison.OrdinalIgnoreCase)
                    && !string.IsNullOrEmpty(t.Industry)
                    && string.Equals(t.Industry, customer.Industry, StringComparison.OrdinalIgnoreCase))
                {
                    matched = t;
                    break;
                }
            }

            // 2. 来源匹配，行业为空（通用）
            if (matched == null)
            {
                foreach (var t in templates)
                {
                    if (string.Equals(t.SourceType, customer.Source, StringComparison.OrdinalIgnoreCase)
                        && string.IsNullOrEmpty(t.Industry))
                    {
                        matched = t;
                        break;
                    }
                }
            }

            // 3. 兜底：其他
            if (matched == null)
            {
                foreach (var t in templates)
                {
                    if (t.SourceType == "其他" && string.IsNullOrEmpty(t.Industry))
                    {
                        matched = t;
                        break;
                    }
                }
            }

            if (matched == null)
            {
                // 终极兜底
                var remark = config.MyTitle;
                var greeting = $"{customer.Name}总您好，我是做展厅多媒体方案的，想跟您交流下，方便吗？";
                return (remark, greeting);
            }

            var remarkResult = ReplaceVariables(matched.RemarkTemplate, customer, config);
            var greetingResult = ReplaceVariables(matched.GreetingTemplateText, customer, config);
            return (remarkResult, greetingResult);
        }

        private static string ReplaceVariables(string template, Customer customer, DailyConfig config)
        {
            var sb = new StringBuilder(template);
            sb.Replace("{Name}", customer.Name);
            sb.Replace("{Phone}", customer.Phone);
            sb.Replace("{Company}", customer.Company);
            sb.Replace("{Industry}", customer.Industry);
            sb.Replace("{Source}", customer.Source);
            sb.Replace("{MyTitle}", config.MyTitle);
            // {Referrer} 提取自Source中的"XX介绍"
            var m = Regex.Match(customer.Source, @"(.+?)介绍");
            sb.Replace("{Referrer}", m.Success ? m.Groups[1].Value : customer.Source);
            return sb.ToString();
        }

        /// <summary>
        /// 批量生成话术
        /// </summary>
        public static void BatchGenerate(List<Customer> customers, DailyConfig config, List<GreetingTemplate> templates)
        {
            foreach (var c in customers)
            {
                if (string.IsNullOrEmpty(c.Remark) || string.IsNullOrEmpty(c.Greeting))
                {
                    var (remark, greeting) = Generate(c, config, templates);
                    c.Remark = remark;
                    c.Greeting = greeting;
                }
            }
        }
    }
}
