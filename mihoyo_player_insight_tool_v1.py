#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 24 22:14:34 2026

@author: xiaoling yin
"""

import json
import time
from collections import Counter

import pandas as pd
from openai import OpenAI

# =========================================
# 1. 基础配置
# =========================================

# 如果已经设置了环境变量 OPENAI_API_KEY，
# 这里直接 OpenAI() 就可以。
# 如果还想临时测试，也可以写成：
# client = OpenAI(api_key="你的key")
client = OpenAI()

MODEL_NAME = "gpt-5.4-mini"   # 先用 mini，更适合练手和控成本
SLEEP_BETWEEN_CALLS = 1.0     # 避免请求太密
OUTPUT_FILE = "mihoyo_player_insight_analysis.xlsx"

# =========================================
# 2. 示例评论数据
# =========================================
# 以后可以很容易改成从 Excel 读取↓[○･｀Д´･ ○]
                            #import pandas as pd
                            # 读取 Excel 文件
                            # 默认读取第一个工作表 (Sheet)
                            #df = pd.read_excel('data.xlsx')
                            # 打印数据前几行
                            #print(df.head())
#现在先假设一些收集到的用户反馈
comments = [
    "新活动剧情很有意思，但奖励太少，打完以后没有继续上线的动力。",
    "这次地图探索做得特别好，音乐和氛围都很有沉浸感。",
    "新角色立绘很好看，但是机制有点复杂，不太想抽。",
    "最近活动有点重复，老玩家可能会觉得缺少新鲜感。",
    "联机体验还不错，但有时候匹配效率太低了。",
    "这次版本前瞻的内容很吸引人，我对后续更新挺期待的。",
    "活动教程太长了，新玩家不一定能快速看懂。",
    "虽然福利一般，但这次角色塑造真的很戳我。",
    "最近有点肝，任务链太长，想轻松一点。",
    "朋友都退坑了，我一个人上线的动力变弱了。"
]

# =========================================
# 3. 职业化分析框架说明
# =========================================
# 这里不是简单做“正负面”就结束，
# 而是尽量模拟用户研究 / 发行运营 / 社区洞察中的文本整理思路。
#
# 单条评论希望输出：
# - sentiment: Positive / Negative / Neutral / Mixed
# - category: 评论主要属于哪类问题
# - topic: 一句话概括评论主题
# - keywords: 关键词
# - player_concern: 玩家核心关注点
# - urgency_level: Low / Medium / High
# - actionable_flag: Yes / No
# - operator_note: 给运营/研究人员的一句简短提示
# - reason: 判断依据
#
# category 我们先统一用有限标签，方便后续汇总：
# - Story / Narrative（剧情叙事）
# - Character（角色设计/抽卡意愿）
# - Event Design（活动设计）
# - Reward / Progression（奖励/成长）
# - Exploration / Immersion（探索/沉浸）
# - Social / Multiplayer（社交/联机）
# - Retention / Engagement（留存/上线动力）
# - Difficulty / Learning Curve（理解门槛/学习成本）
# - Fatigue / Grind（疲劳/肝度）
# - Technical / UX（技术/交互体验）
# - Marketing / Promotion（宣发/版本前瞻）
# - Other（其他）
#
# 这样做的职业意义：
# 1. 可以把玩家反馈从“自然语言”变成“结构化标签”
# 2. 方便后面做主题统计和优先级排序
# 3. 方便把结果给运营、社区、发行、用户研究同事看

# =========================================
# 4. 单条评论分析函数
# =========================================
def analyze_comment(comment: str, model_name: str = MODEL_NAME) -> dict:
    """
    使用 LLM 对单条玩家评论做结构化分析。
    要求模型只输出 JSON，避免后续解析困难。
    """
    prompt = f"""
你是一名游戏用户研究与发行运营分析助手。
你的任务是对单条玩家评论做结构化分析，输出给用户研究、社区运营、发行支持团队参考。

请严格只输出 JSON，不要输出任何额外文字。
请使用以下 JSON 格式：

{{
  "sentiment": "Positive/Negative/Neutral/Mixed",
  "category": "从以下类别中选择一个：Story / Character / Event Design / Reward / Progression / Exploration / Immersion / Social / Multiplayer / Retention / Engagement / Difficulty / Learning Curve / Fatigue / Grind / Technical / UX / Marketing / Promotion / Other",
  "topic": "一句中文概括主题",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "player_concern": "这条评论反映的玩家核心关注点",
  "urgency_level": "Low/Medium/High",
  "actionable_flag": "Yes/No",
  "operator_note": "给运营/用户研究团队的一句简短建议",
  "reason": "一句中文说明你的判断依据"
}}

分析原则：
1. 不要过度脑补，只基于评论内容本身判断。
2. 如果评论同时包含正负面因素，可以标记为 Mixed。
3. urgency_level 的判断逻辑：
   - High：明显影响留存、满意度、版本体验或传播风险
   - Medium：有明确改进价值，但不一定是核心阻碍
   - Low：偏轻度反馈、一般性表扬或弱抱怨
4. actionable_flag = Yes，代表该评论适合进入后续运营/研究整理池。
5. operator_note 要尽量像业务提示，例如：
   - 建议关注老玩家疲劳感
   - 可进一步验证新玩家理解门槛
   - 可纳入角色机制反馈汇总

玩家评论：
{comment}
"""

    response = client.responses.create(
        model=model_name,
        input=prompt
    )

    text = response.output_text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {
            "sentiment": "ParseError",
            "category": "",
            "topic": "",
            "keywords": [],
            "player_concern": "",
            "urgency_level": "",
            "actionable_flag": "No",
            "operator_note": "",
            "reason": text
        }

    return result

# =========================================
# 5. 批量分析函数
# =========================================
def analyze_comments(comment_list: list[str]) -> pd.DataFrame:
    """
    对评论列表批量分析，返回结构化 DataFrame。
    """
    results = []

    total = len(comment_list)
    print(f"准备分析 {total} 条玩家评论...\n")

    for idx, comment in enumerate(comment_list, start=1):
        print(f"正在分析第 {idx}/{total} 条评论...")

        try:
            result = analyze_comment(comment)

            keywords = result.get("keywords", [])
            if isinstance(keywords, list):
                keywords_str = ", ".join(keywords)
            else:
                keywords_str = str(keywords)

            results.append({
                "comment_id": idx,
                "comment": comment,
                "sentiment": result.get("sentiment", ""),
                "category": result.get("category", ""),
                "topic": result.get("topic", ""),
                "keywords": keywords_str,
                "player_concern": result.get("player_concern", ""),
                "urgency_level": result.get("urgency_level", ""),
                "actionable_flag": result.get("actionable_flag", ""),
                "operator_note": result.get("operator_note", ""),
                "reason": result.get("reason", "")
            })

        except Exception as e:
            results.append({
                "comment_id": idx,
                "comment": comment,
                "sentiment": "Error",
                "category": "",
                "topic": "",
                "keywords": "",
                "player_concern": "",
                "urgency_level": "",
                "actionable_flag": "No",
                "operator_note": "",
                "reason": str(e)
            })

        time.sleep(SLEEP_BETWEEN_CALLS)

    df = pd.DataFrame(results)
    return df

# =========================================
# 6. 汇总分析函数
# =========================================
def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    根据单条评论分析结果，生成一个简要 summary 表。
    这一步尽量模拟“给运营/用户研究看的日报/小结”。
    """
    summary_rows = []

    total_comments = len(df)
    sentiment_counts = Counter(df["sentiment"])
    category_counts = Counter(df["category"])
    urgency_counts = Counter(df["urgency_level"])
    actionable_counts = Counter(df["actionable_flag"])

    # 1. 基本统计
    summary_rows.append({
        "metric": "总评论数",
        "value": total_comments
    })

    for k, v in sentiment_counts.items():
        summary_rows.append({
            "metric": f"情绪分布 - {k}",
            "value": v
        })

    for k, v in urgency_counts.items():
        summary_rows.append({
            "metric": f"优先级分布 - {k}",
            "value": v
        })

    for k, v in actionable_counts.items():
        summary_rows.append({
            "metric": f"是否建议跟进 - {k}",
            "value": v
        })

    # 2. 高频主题类别 Top 5
    for cat, count in category_counts.most_common(5):
        summary_rows.append({
            "metric": f"高频类别 - {cat}",
            "value": count
        })

    # 3. 负面/混合评论重点看哪些类别
    negative_df = df[df["sentiment"].isin(["Negative", "Mixed"])]
    if not negative_df.empty:
        neg_category_counts = Counter(negative_df["category"])
        for cat, count in neg_category_counts.most_common(5):
            summary_rows.append({
                "metric": f"负面/混合高频类别 - {cat}",
                "value": count
            })

    summary_df = pd.DataFrame(summary_rows)
    return summary_df

# =========================================
# 7. 导出 Excel
# =========================================
def export_to_excel(detail_df: pd.DataFrame, summary_df: pd.DataFrame, output_file: str):
    """
    导出两个 sheet：
    1. comment_analysis：单条评论分析结果
    2. summary：汇总信息
    """
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="comment_analysis", index=False)
        summary_df.to_excel(writer, sheet_name="summary", index=False)

    print(f"\n已导出 Excel 文件：{output_file}")

# =========================================
# 8. 主程序
# =========================================
def main():
    detail_df = analyze_comments(comments)

    print("\n单条评论分析预览：")
    print(detail_df.head())

    summary_df = build_summary(detail_df)

    print("\n汇总结果预览：")
    print(summary_df.head(20))

    export_to_excel(detail_df, summary_df, OUTPUT_FILE)

    print("\n项目完成。")
    print("你现在得到的是一个更接近“用户研究/发行支持”思路的玩家反馈分析原型。")

if __name__ == "__main__":
    main()
    
    
    
    
    
    
    