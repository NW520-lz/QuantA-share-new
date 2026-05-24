# AI 配置与选股策略说明

---

## 一、DeepSeek API 配置

### 1. 环境变量 (.env)

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_TIMEOUT_SECONDS=60
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥，在 [platform.deepseek.com](https://platform.deepseek.com/api_keys) 获取 | 必填 |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-v4-pro` |
| `DEEPSEEK_TIMEOUT_SECONDS` | 请求超时（秒） | `60` |

### 2. 思考模式 (Thinking Mode)

`deepseek-v4-pro` 已启用思考模式，模型将在输出最终回答前进行思维链推理，提升答案准确性。

**请求参数**（在 `deepseek_client.py` 中已配置）：

```json
{
    "thinking": {"type": "enabled"},
    "reasoning_effort": "high"
}
```

### 3. 工具调用 (Tool Calls)

思考模式下支持工具调用，模型可以：

1. **思考** → 判断需要哪种工具
2. **调用工具** → 获取实时 A 股数据
3. **继续思考** → 结合数据进行量化分析
4. **输出结果** → 结构化量化报告

#### 工具调用消息拼接规则

| 场景 | reasoning_content 处理 |
|------|----------------------|
| 未进行工具调用 | 不参与后续上下文拼接 |
| 进行了工具调用 | 必须回传给 API（否则 400 错误） |

代码已按 DeepSeek 官方规范处理，详见 `backend/app/services/ai/deepseek_client.py:106-113`。

#### 可用工具清单

| 工具名称 | 功能 | 数据源 |
|----------|------|--------|
| `search_stocks` | 搜索 A 股标的（代码/名称模糊匹配） | baostock |
| `get_stock_data` | 日线 OHLCV K 线数据 | baostock |
| `full_analysis` | 全维度分析（趋势+量能+风险+回测） | 综合 |
| `analyze_trend` | MA 排列/方向/评分 | baostock |
| `analyze_volume` | 放量/缩量/VWAP | baostock |
| `assess_risk` | 波动率/回撤/仓位限制 | baostock |
| `run_backtest` | Swing 策略回测 | baostock |
| `get_scan_status` | 全 A 扫描进度 | 数据库 |
| `get_top_candidates` | Top 候选排行 | 数据库 |
| `get_market_sentiment` | 市场情绪指标 | 数据库 |
| `explain_strategy` | 策略规则说明 | 静态 |
| `get_system_info` | 系统功能介绍 | 静态 |
| `web_search` | 联网搜索（Tavily + Brave 双引擎） | Web |

### 4. 调用链路

```
用户提问 → DeepSeek (思考模式) → 工具调用 → 数据获取 → DeepSeek (思考模式) → 最终回答
             ↓ 失败                      ↓ 失败                      ↓ 失败
         GitHub Models             GitHub Models              Nuwax
```

---

## 二、数据源配置

### 优先级

```
baostock（主） → akshare（备）
```

实现位置：`backend/app/services/data/baostock.py`

- **日线数据**：先尝试 baostock，失败后自动降级到 akshare
- **股票列表**：使用 akshare 获取全 A 股列表（含市值、行业）
- **扫描器**：统一使用 `get_daily_data()` 接口，遵循上述优先级

---

## 三、选股策略 — 极严格涨停预测

### 1. 策略概述

全市场扫描采用极严格多因子共振条件，目标是筛选**次日极大概率涨停**的标的。

### 2. 评分体系（满分 12）

| 因子 | 条件 | 分值 |
|------|------|------|
| trend_ma_cross | MA5 > MA10 > MA20 > MA30，MA20 拐头向上 | +1 |
| ma_golden_cross | MA5 上穿 MA10，MA10 > MA20 | +1 |
| breakout_volume | 低位横盘后 7%+ 放量阳线 | +1 |
| pullback_hold | 回踩 MA10/MA20 止跌，收盘站回均线 | +1 |
| volume_ratio_strong | 量比 >= 1.5 | +1 |
| volume_surge_extreme | 量比 >= 2.5（超强放量） | +1 |
| close_near_high | R 值 >= 0.8（收盘接近日高） | +1 |
| long_term_low | 近 120 日相对低位 | +1 |
| recent_limit_up_20d | 近 20 日有涨停 | +1 |
| yy_trend_filter_pass | Y1-Y4 积累模式通过 | +1 |
| limitup_breakout_signal | 涨停回调突破确认 | +2 |

### 3. 绿色买入条件

#### Pattern A — 涨停回调突破（最强信号）

| 条件 | 阈值 |
|------|------|
| 涨停回调突破 | 确认（回调不破支撑 + 低位 + 强势 + 能破压力 + 突破进攻线） |
| 综合得分 | >= 7 分 |
| 量比 | >= 2.5 倍（近 5 日均量） |
| R 值 | >= 0.8（收盘在日 K 上端） |

#### Pattern B — MA 金叉共振 + YY 积累 + 放量突破

| 条件 | 阈值 |
|------|------|
| 趋势向上 | MA5 > MA10 > MA20 > MA30，MA20 上翘 |
| MA 金叉 | MA5 上穿 MA10 |
| 买入触发 | 放量突破 / 回踩确认 / 涨停突破（任一） |
| 综合得分 | >= 7 分 |
| 量比 | >= 2.5 倍 |
| R 值 | >= 0.8 |
| 涨停基因 | 近 20 日有涨停 |
| YY 积累 | 7 天小阳线 + MA 排列 + 均线上扬 + 量能活跃 |

### 4. 信号类型

| 类型 | 优先级 | 说明 |
|------|--------|------|
| `limitup_breakout` | 最高 | 涨停回调后突破进攻线，最可能次日涨停 |
| `pullback` | 高 | 回踩均线止跌反弹 |
| `breakout` | 中 | 低位横盘后放量突破 |
| `trend` | 低 | 趋势跟随 |

### 5. YY 过滤器详解

| 条件 | 规则 |
|------|------|
| Y1 | 连续 7 天小阳线（每天收阳、涨幅 < 3%） |
| Y2 | MA5 > MA10 > MA20（多头排列） |
| Y3 | MA5/10/20 连续 3 天同向上升 |
| Y4 | 量能活跃（量比 >= 1.2）+ 成交额 > 3000 万 + 未急涨 |

### 6. 涨停回调突破策略详解

```
涨停:= C/REF(C,1) > 1.097 AND C = H
周期:= 涨停次日非涨停距今的天数（≤ 30 天）
支撑:= 涨停日前日低点
压力:= 周期内最高 O/H
进攻线:= MAX(涨停日 C/O, 涨停前日 C/O)

买入信号:
  周期内不破支撑 + 低位(10日振幅<50%)
  + 强势(15日高*1.1 > 30日高)
  + 能破压力(当前价*1.11 > 压力)
  + 收盘突破进攻线(昨收 ≤ 进攻线 < 今收)
  + 量能确认(涨停日±3日量比>=1.5)
  + 成交额(近3日均>=2000万)
```

### 7. 信号颜色分级

| 颜色 | 含义 | 条件 |
|------|------|------|
| 绿色 | 极严格买入 | 满足 Pattern A 或 Pattern B |
| 黄色 | 观察候选 | 得分 >= 4 但未满足严格条件 |
| 红色 | 不符合 | 得分 < 4 |

### 8. 仓位建议

| 得分 | 建议仓位 |
|------|----------|
| >= 7 | 80% |
| 5-6 | 60% |
| 4 | 40% |
| 3 | 20% |

---

## 四、扫描器配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `BATCH_SIZE` | 50 | 每批扫描数量 |
| `CONCURRENT` | 8 | 并发数 |
| `DAYS_LOOKBACK` | 90 | 日线回溯天数 |
| `SCAN_INTERVAL_HOURS` | 2 | 扫描间隔 |

实现位置：`backend/app/services/scanner.py`

---

## 五、技术架构

```
┌─────────────────────────────────────────────────┐
│                   前端 HTML/JS                   │
│              选股看板 / AI 对话 / 持仓风控          │
└───────────────────┬─────────────────────────────┘
                    │ HTTP/SSE
┌───────────────────┴─────────────────────────────┐
│              FastAPI (uvicorn)                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ AI Chat  │  │Scan Board│  │  Auth/Billing │ │
│  └────┬─────┘  └────┬─────┘  └───────────────┘ │
│       │              │                           │
│  ┌────┴──────────────┴───────────────────────┐  │
│  │              AI Service                    │  │
│  │  DeepSeek → GitHub Models → Nuwax          │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │           Strategy Engine                  │  │
│  │  Swing + YY Filter + LimitUp Breakout      │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │           Data Layer                       │  │
│  │  baostock (主) → akshare (备)              │  │
│  └───────────────────────────────────────────┘  │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────┴─────────────────────────────┐
│           PostgreSQL (scan_results)              │
└─────────────────────────────────────────────────┘
```
