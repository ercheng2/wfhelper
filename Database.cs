using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.Data.Sqlite;

namespace WeChatFriendHelper
{
    public enum AddStatus
    {
        Pending,      // 待添加
        Sent,         // 已发送
        Accepted,     // 已通过
        Rejected,     // 未通过
        Retry         // 待重试
    }

    public class Customer
    {
        public int Id { get; set; }
        public string Name { get; set; } = "";
        public string Phone { get; set; } = "";
        public string Company { get; set; } = "";
        public string Industry { get; set; } = "";
        public string Source { get; set; } = "";
        public AddStatus Status { get; set; } = AddStatus.Pending;
        public string Remark { get; set; } = "";        // 添加备注
        public string Greeting { get; set; } = "";      // 打招呼话术
        public DateTime CreatedAt { get; set; } = DateTime.Now;
        public DateTime? SentAt { get; set; }            // 发送添加请求的时间
        public DateTime? AcceptedAt { get; set; }        // 通过时间
        public int RetryCount { get; set; } = 0;
        public int MaxRetry { get; set; } = 3;
        public string Notes { get; set; } = "";          // 自定义备注
    }

    public class GreetingTemplate
    {
        public int Id { get; set; }
        public string SourceType { get; set; } = "";     // 来源类型：展会/同行介绍/行业筛选/其他
        public string Industry { get; set; } = "";       // 行业（空=通用）
        public string RemarkTemplate { get; set; } = ""; // 备注模板
        public string GreetingTemplateText { get; set; } = ""; // 话术模板
    }

    public class DailyConfig
    {
        public int DailyLimit { get; set; } = 25;
        public int RetryDays { get; set; } = 3;         // 未通过几天后重试
        public string MyTitle { get; set; } = "双诚科技-黄工";
    }

    public class Database : IDisposable
    {
        private readonly SqliteConnection _conn;
        private readonly string _dbPath;

        public Database()
        {
            var dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "WeChatFriendHelper");
            Directory.CreateDirectory(dir);
            _dbPath = Path.Combine(dir, "data.db");
            _conn = new SqliteConnection($"Data Source={_dbPath}");
            _conn.Open();
            InitTables();
        }

        private void InitTables()
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = @"
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    company TEXT DEFAULT '',
                    industry TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    status INTEGER DEFAULT 0,
                    remark TEXT DEFAULT '',
                    greeting TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    sent_at TEXT,
                    accepted_at TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retry INTEGER DEFAULT 3,
                    notes TEXT DEFAULT '',
                    UNIQUE(phone)
                );

                CREATE TABLE IF NOT EXISTS greeting_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT DEFAULT '',
                    industry TEXT DEFAULT '',
                    remark_template TEXT DEFAULT '',
                    greeting_template TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                INSERT OR IGNORE INTO greeting_templates (source_type, industry, remark_template, greeting_template) VALUES
                    ('展会', '', '{MyTitle}，{Source}展会', '{Name}总您好，{Source}展会上了解到贵司有展厅项目，我们做过类似案例，方便发您参考吗？'),
                    ('同行介绍', '', '{MyTitle}，{Referrer}推荐', '{Name}总您好，听{Referrer}提到贵司在做展厅升级，我们专注展厅多媒体方案，加您发些案例'),
                    ('行业筛选', '', '{MyTitle}，展厅方案咨询', '{Name}总您好，看到贵司在展厅方向有业务，我们做展厅多媒体集成，加个微信交流下？'),
                    ('其他', '', '{MyTitle}', '{Name}总您好，我是做展厅多媒体方案的，想跟您交流下，方便吗？'),
                    ('展会', '展览展示', '{MyTitle}，{Source}展会', '{Name}总您好，{Source}展会上了解到贵司做展览展示，我们专注展厅多媒体集成，有不少案例可以分享'),
                    ('行业筛选', '博物馆', '{MyTitle}，博物馆方案咨询', '{Name}总您好，了解到贵司有博物馆项目，我们在文博展厅多媒体方面经验丰富，方便交流下吗？');
            ";
            cmd.ExecuteNonQuery();
        }

        // ========== Customer CRUD ==========
        public List<Customer> GetAllCustomers()
        {
            var list = new List<Customer>();
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "SELECT * FROM customers ORDER BY created_at DESC";
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                list.Add(ReadCustomer(reader));
            }
            return list;
        }

        public List<Customer> GetCustomersByStatus(AddStatus status)
        {
            var list = new List<Customer>();
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "SELECT * FROM customers WHERE status=@status ORDER BY created_at DESC";
            cmd.Parameters.AddWithValue("@status", (int)status);
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                list.Add(ReadCustomer(reader));
            }
            return list;
        }

        public int GetTodaySentCount()
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "SELECT COUNT(*) FROM customers WHERE status=@sent AND date(sent_at)=date('now','localtime')";
            cmd.Parameters.AddWithValue("@sent", (int)AddStatus.Sent);
            return Convert.ToInt32(cmd.ExecuteScalar());
        }

        public List<Customer> GetRetryCustomers()
        {
            var list = new List<Customer>();
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = @"
                SELECT * FROM customers 
                WHERE status=@rejected 
                AND retry_count < max_retry 
                AND julianday('now','localtime') - julianday(sent_at) >= 3
                ORDER BY sent_at ASC";
            cmd.Parameters.AddWithValue("@rejected", (int)AddStatus.Rejected);
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                list.Add(ReadCustomer(reader));
            }
            return list;
        }

        public int InsertCustomer(Customer c)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = @"
                INSERT OR IGNORE INTO customers (name, phone, company, industry, source, status, remark, greeting, notes)
                VALUES (@name, @phone, @company, @industry, @source, @status, @remark, @greeting, @notes);
                SELECT last_insert_rowid();";
            cmd.Parameters.AddWithValue("@name", c.Name);
            cmd.Parameters.AddWithValue("@phone", c.Phone);
            cmd.Parameters.AddWithValue("@company", c.Company ?? "");
            cmd.Parameters.AddWithValue("@industry", c.Industry ?? "");
            cmd.Parameters.AddWithValue("@source", c.Source ?? "");
            cmd.Parameters.AddWithValue("@status", (int)c.Status);
            cmd.Parameters.AddWithValue("@remark", c.Remark ?? "");
            cmd.Parameters.AddWithValue("@greeting", c.Greeting ?? "");
            cmd.Parameters.AddWithValue("@notes", c.Notes ?? "");
            var result = cmd.ExecuteScalar();
            return result != null ? Convert.ToInt32(result) : 0;
        }

        public void UpdateCustomer(Customer c)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = @"
                UPDATE customers SET 
                    name=@name, phone=@phone, company=@company, industry=@industry, 
                    source=@source, status=@status, remark=@remark, greeting=@greeting,
                    sent_at=@sent_at, accepted_at=@accepted_at, 
                    retry_count=@retry_count, max_retry=@max_retry, notes=@notes
                WHERE id=@id";
            cmd.Parameters.AddWithValue("@id", c.Id);
            cmd.Parameters.AddWithValue("@name", c.Name);
            cmd.Parameters.AddWithValue("@phone", c.Phone);
            cmd.Parameters.AddWithValue("@company", c.Company ?? "");
            cmd.Parameters.AddWithValue("@industry", c.Industry ?? "");
            cmd.Parameters.AddWithValue("@source", c.Source ?? "");
            cmd.Parameters.AddWithValue("@status", (int)c.Status);
            cmd.Parameters.AddWithValue("@remark", c.Remark ?? "");
            cmd.Parameters.AddWithValue("@greeting", c.Greeting ?? "");
            cmd.Parameters.AddWithValue("@sent_at", c.SentAt?.ToString("yyyy-MM-dd HH:mm:ss") ?? (object)DBNull.Value);
            cmd.Parameters.AddWithValue("@accepted_at", c.AcceptedAt?.ToString("yyyy-MM-dd HH:mm:ss") ?? (object)DBNull.Value);
            cmd.Parameters.AddWithValue("@retry_count", c.RetryCount);
            cmd.Parameters.AddWithValue("@max_retry", c.MaxRetry);
            cmd.Parameters.AddWithValue("@notes", c.Notes ?? "");
            cmd.ExecuteNonQuery();
        }

        public void DeleteCustomer(int id)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "DELETE FROM customers WHERE id=@id";
            cmd.Parameters.AddWithValue("@id", id);
            cmd.ExecuteNonQuery();
        }

        // ========== Greeting Templates ==========
        public List<GreetingTemplate> GetAllTemplates()
        {
            var list = new List<GreetingTemplate>();
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "SELECT * FROM greeting_templates ORDER BY source_type, industry";
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                list.Add(new GreetingTemplate
                {
                    Id = reader.GetInt32(0),
                    SourceType = reader.GetString(1),
                    Industry = reader.GetString(2),
                    RemarkTemplate = reader.GetString(3),
                    GreetingTemplateText = reader.GetString(4)
                });
            }
            return list;
        }

        public void InsertTemplate(GreetingTemplate t)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "INSERT INTO greeting_templates (source_type, industry, remark_template, greeting_template) VALUES (@st, @ind, @rt, @gt)";
            cmd.Parameters.AddWithValue("@st", t.SourceType);
            cmd.Parameters.AddWithValue("@ind", t.Industry);
            cmd.Parameters.AddWithValue("@rt", t.RemarkTemplate);
            cmd.Parameters.AddWithValue("@gt", t.GreetingTemplateText);
            cmd.ExecuteNonQuery();
        }

        public void DeleteTemplate(int id)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "DELETE FROM greeting_templates WHERE id=@id";
            cmd.Parameters.AddWithValue("@id", id);
            cmd.ExecuteNonQuery();
        }

        // ========== Config ==========
        public DailyConfig GetConfig()
        {
            var config = new DailyConfig();
            using var cmd = _conn.CreateCommand();
            
            cmd.CommandText = "SELECT value FROM config WHERE key='DailyLimit'";
            var val = cmd.ExecuteScalar();
            if (val != null) config.DailyLimit = int.Parse(val.ToString()!);

            cmd.CommandText = "SELECT value FROM config WHERE key='RetryDays'";
            val = cmd.ExecuteScalar();
            if (val != null) config.RetryDays = int.Parse(val.ToString()!);

            cmd.CommandText = "SELECT value FROM config WHERE key='MyTitle'";
            val = cmd.ExecuteScalar();
            if (val != null) config.MyTitle = val.ToString()!;

            return config;
        }

        public void SaveConfig(DailyConfig config)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = @"
                INSERT OR REPLACE INTO config (key, value) VALUES ('DailyLimit', @dl);
                INSERT OR REPLACE INTO config (key, value) VALUES ('RetryDays', @rd);
                INSERT OR REPLACE INTO config (key, value) VALUES ('MyTitle', @mt);";
            cmd.Parameters.AddWithValue("@dl", config.DailyLimit.ToString());
            cmd.Parameters.AddWithValue("@rd", config.RetryDays.ToString());
            cmd.Parameters.AddWithValue("@mt", config.MyTitle);
            cmd.ExecuteNonQuery();
        }

        // ========== Statistics ==========
        public Dictionary<string, int> GetStatusCounts()
        {
            var dict = new Dictionary<string, int>();
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = @"
                SELECT 
                    SUM(CASE WHEN status=0 THEN 1 ELSE 0 END) AS Pending,
                    SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) AS Sent,
                    SUM(CASE WHEN status=2 THEN 1 ELSE 0 END) AS Accepted,
                    SUM(CASE WHEN status=3 THEN 1 ELSE 0 END) AS Rejected,
                    SUM(CASE WHEN status=4 THEN 1 ELSE 0 END) AS Retry,
                    COUNT(*) AS Total
                FROM customers";
            using var reader = cmd.ExecuteReader();
            if (reader.Read())
            {
                dict["Pending"] = reader.GetInt32(0);
                dict["Sent"] = reader.GetInt32(1);
                dict["Accepted"] = reader.GetInt32(2);
                dict["Rejected"] = reader.GetInt32(3);
                dict["Retry"] = reader.GetInt32(4);
                dict["Total"] = reader.GetInt32(5);
            }
            return dict;
        }

        public List<(string Date, int Sent, int Accepted)> GetDailyStats(int days = 30)
        {
            var list = new List<(string, int, int)>();
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = @"
                SELECT date(sent_at) as d, 
                       COUNT(*) as sent_count,
                       SUM(CASE WHEN status=2 THEN 1 ELSE 0 END) as accepted_count
                FROM customers 
                WHERE sent_at >= date('now','localtime', '-' || @days || ' days')
                GROUP BY date(sent_at)
                ORDER BY d";
            cmd.Parameters.AddWithValue("@days", days.ToString());
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                list.Add((reader.GetString(0), reader.GetInt32(1), reader.GetInt32(2)));
            }
            return list;
        }

        private Customer ReadCustomer(SqliteDataReader reader)
        {
            return new Customer
            {
                Id = reader.GetInt32(0),
                Name = reader.GetString(1),
                Phone = reader.GetString(2),
                Company = reader.IsDBNull(3) ? "" : reader.GetString(3),
                Industry = reader.IsDBNull(4) ? "" : reader.GetString(4),
                Source = reader.IsDBNull(5) ? "" : reader.GetString(5),
                Status = (AddStatus)reader.GetInt32(6),
                Remark = reader.IsDBNull(7) ? "" : reader.GetString(7),
                Greeting = reader.IsDBNull(8) ? "" : reader.GetString(8),
                CreatedAt = DateTime.Parse(reader.GetString(9)),
                SentAt = reader.IsDBNull(10) ? null : DateTime.Parse(reader.GetString(10)),
                AcceptedAt = reader.IsDBNull(11) ? null : DateTime.Parse(reader.GetString(11)),
                RetryCount = reader.IsDBNull(12) ? 0 : reader.GetInt32(12),
                MaxRetry = reader.IsDBNull(13) ? 3 : reader.GetInt32(13),
                Notes = reader.IsDBNull(14) ? "" : reader.GetString(14)
            };
        }

        public void Dispose()
        {
            _conn?.Close();
            _conn?.Dispose();
        }
    }
}
