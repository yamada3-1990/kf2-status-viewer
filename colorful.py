import streamlit as st
import pandas as pd
import requests
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- 定数と設定 ---

# ゲーム名とSteam AppIDの対応表
GAME_APP_IDS = {
    "Killing Floor 2": 232090,
}

# Perkのレベルアップに必要な累計経験値のテーブル
CUMULATIVE_XP_PER_LEVEL = [
    0, 2640, 5557, 8781, 12343, 16279, 20628, 25434, 30745, 36613,
    43097, 50262, 58180, 66929, 76596, 87279, 99083, 112127, 126540,
    142467, 160066, 179513, 201002, 224747, 250985, 279978
]

# 最大レベルと必要ポイント
MAX_PERK_LEVEL = 25
MAX_PRESTIGE_LEVEL = 2
WELDING_POINTS_REQUIRED = 510
HEALING_POINTS_REQUIRED = 10
KFMAX_PERKS = 10

# KF2のPerk統計ID（APIデータより）
PERK_STAT_IDS = {
    "Commando": {"progress": 1, "build": 2, "icon": "🎯"},
    "Berserker": {"progress": 10, "build": 11, "icon": "⚔️"},
    "Support": {"progress": 20, "build": 21, "weld": 22, "icon": "🔧"},
    "Firebug": {"progress": 30, "build": 31, "icon": "🔥"},
    "Field Medic": {"progress": 40, "build": 41, "heal": 42, "icon": "🏥"},
    "Sharpshooter": {"progress": 50, "build": 51, "icon": "🎯"},
    "Demolitionist": {"progress": 60, "build": 61, "icon": "💥"},
    "Survivalist": {"progress": 70, "build": 71, "icon": "🏃"},
    "Gunslinger": {"progress": 80, "build": 81, "icon": "🔫"},
    "SWAT": {"progress": 90, "build": 91, "icon": "🛡️"},
}

# 各種統計マッピング
KILL_STAT_IDS = {
    "総キル数": 200,
    "ストーカー討伐": 201,
    "クローラー討伐": 202,
    "フレッシュパウンド討伐": 203,
}

PERSONAL_BEST_IDS = {
    "ナイフキル": 2000,
    "ピストルキル": 2001,
    "ヘッドショット": 2002,
    "ヒール量": 2003,
    "総キル": 2004,
    "アシスト": 2005,
    "大型ZED討伐": 2006,
    "DOSH獲得": 2007,
}

ACHIEVEMENT_IDS = {
    "MrPerky5": 4001,
    "MrPerky10": 4002,
    "MrPerky15": 4003,
    "MrPerky20": 4004,
    "MrPerky25": 4005,
    "Hard勝利": 4015,
    "Suicidal勝利": 4016,
    "Hell勝利": 4017,
    "VSZed勝利": 4009,
    "VSHuman勝利": 4010,
    "HoldOut": 4011,
    "DieVolter": 4012,
    "FleshPound討伐": 4013,
    "Shrike討伐": 4014,
    "Siren討伐": 4018,
    "Benefactor": 4019,
    "HealTeam": 4020,
    "QuickOnTheTrigger": 4033,
}

# --- データ取得関数 ---

def get_player_playtime(api_key, steam_id, app_id):
    """指定されたゲームの総プレイ時間（分）を取得する"""
    try:
        url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={api_key}&steamid={steam_id}&format=json"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json().get("response", {}).get("games", [])
        for game in data:
            if game["appid"] == app_id:
                return game.get("playtime_forever", 0)
        return 0
    except requests.exceptions.RequestException as e:
        st.error(f"プレイ時間取得中にAPIエラーが発生しました: {e}")
        return 0

def get_player_stats(api_key, steam_id, app_id):
    """指定されたゲームの戦績と実績を取得する"""
    try:
        url = f"https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v0002/?appid={app_id}&key={api_key}&steamid={steam_id}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("playerstats")
    except requests.exceptions.RequestException as e:
        st.error(f"戦績データ取得中にAPIエラーが発生しました: {e}")
        return None

def get_total_achievements(api_key, app_id):
    """ゲームの全実績数を取得する"""
    try:
        url = f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?key={api_key}&appid={app_id}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        achievements_schema = data.get("game", {}).get("availableGameStats", {}).get("achievements", [])
        return len(achievements_schema)
    except requests.exceptions.RequestException as e:
        st.error(f"全実績数の取得中にAPIエラーが発生しました: {e}")
        return 0

def get_game_schema(api_key, app_id):
    """ゲームのスキーマ情報（統計、実績）を取得する"""
    try:
        url = f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?key={api_key}&appid={app_id}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json().get("game", {}).get("availableGameStats", {})
        
        stats_schema = {stat["name"]: stat.get("displayName", stat["name"]) for stat in data.get("stats", [])}
        
        achievements_schema = {
            ach["name"]: {
                "displayName": ach.get("displayName", ach["name"]),
                "description": ach.get("description", ""),
                "icon": ach.get("icon", ""),
            }
            for ach in data.get("achievements", [])
        }
        
        return {"stats": stats_schema, "achievements": achievements_schema}
    except Exception as e:
        st.error(f"ゲームスキーマの取得中にエラーが発生しました: {e}")
        return {"stats": {}, "achievements": {}}

# --- データ処理関数 ---

def get_stat_value(stats_dict, stat_id):
    """統計IDから値を取得する"""
    return stats_dict.get(f"1_{stat_id}", 0)

def calculate_perk_level_info(xp):
    """総経験値(XP)からPerkのレベル、進捗、次のレベルまでの必要XPを計算する"""
    if xp >= CUMULATIVE_XP_PER_LEVEL[-1]:
        return 25, 100.0, 0

    level = 0
    for i, required_xp in enumerate(CUMULATIVE_XP_PER_LEVEL):
        if xp < required_xp:
            level = i - 1
            if level < 0: 
                level = 0
            
            xp_for_current_level = CUMULATIVE_XP_PER_LEVEL[level]
            progress_in_level = xp - xp_for_current_level
            needed_for_levelup = required_xp - xp_for_current_level
            
            if needed_for_levelup == 0:
                progress_percent = 100.0
            else:
                progress_percent = (progress_in_level / needed_for_levelup) * 100
            
            return level, progress_percent, required_xp - xp
            
    return 0, 0.0, CUMULATIVE_XP_PER_LEVEL[1] - xp

def analyze_kf2_stats(stats_dict):
    """KF2統計データを詳細に分析する"""
    analysis = {}
    
    # Perkデータの分析
    perks = {}
    for perk_name, ids in PERK_STAT_IDS.items():
        progress_xp = get_stat_value(stats_dict, ids["progress"])
        build_xp = get_stat_value(stats_dict, ids["build"])
        
        if progress_xp > 0 or build_xp > 0:
            # 進捗XPが主要な値のようだ
            total_xp = progress_xp if progress_xp > 0 else build_xp
            level, progress_percent, next_level_xp = calculate_perk_level_info(total_xp)
            
            perks[perk_name] = {
                "level": level,
                "xp": total_xp,
                "progress_percent": progress_percent,
                "next_level_xp": next_level_xp,
                "is_max": level >= MAX_PERK_LEVEL,
                "icon": ids["icon"]
            }
            
            # 特別な統計
            if perk_name == "Support" and "weld" in ids:
                perks[perk_name]["weld_points"] = get_stat_value(stats_dict, ids["weld"])
            elif perk_name == "Field Medic" and "heal" in ids:
                perks[perk_name]["heal_points"] = get_stat_value(stats_dict, ids["heal"])
    
    analysis["perks"] = perks
    
    # キル統計
    kills = {}
    for kill_name, stat_id in KILL_STAT_IDS.items():
        kills[kill_name] = get_stat_value(stats_dict, stat_id)
    analysis["kills"] = kills
    
    # パーソナルベスト
    personal_bests = {}
    for pb_name, stat_id in PERSONAL_BEST_IDS.items():
        personal_bests[pb_name] = get_stat_value(stats_dict, stat_id)
    analysis["personal_bests"] = personal_bests
    
    # 実績進捗（統計データベース）
    achievements = {}
    for ach_name, stat_id in ACHIEVEMENT_IDS.items():
        achievements[ach_name] = get_stat_value(stats_dict, stat_id)
    analysis["achievements"] = achievements
    
    # 特別な統計
    analysis["special_stats"] = {
        "special_event_progress": get_stat_value(stats_dict, 300),
        "weekly_event_progress": get_stat_value(stats_dict, 301),
        "daily_event_info": get_stat_value(stats_dict, 302),
        "dosh_vault_total": get_stat_value(stats_dict, 400),
        "dosh_vault_progress": get_stat_value(stats_dict, 402),
        "match_wins": get_stat_value(stats_dict, 3000),
    }
    
    return analysis

# --- UI表示関数 ---

def display_overview_dashboard(analysis, playtime_minutes):
    """概要ダッシュボードを表示する"""
    st.markdown("### 📊 概要ダッシュボード")
    
    perks = analysis.get("perks", {})
    kills = analysis.get("kills", {})
    personal_bests = analysis.get("personal_bests", {})
    special_stats = analysis.get("special_stats", {})
    
    # 主要指標
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_perks = len(perks)
        max_level_perks = sum(1 for perk in perks.values() if perk["is_max"])
        st.metric(
            "🎯 MAX Perks",
            f"{max_level_perks}/{total_perks}",
            delta=f"{(max_level_perks/total_perks*100):.1f}% 完了" if total_perks > 0 else None
        )
    
    with col2:
        total_kills = kills.get("総キル数", 0)
        st.metric(
            "👹 総キル数",
            f"{total_kills:,}",
            delta=f"{total_kills/max(1, playtime_minutes/60):.1f} kills/h" if playtime_minutes > 0 else None
        )
    
    with col3:
        best_headshots = personal_bests.get("ヘッドショット", 0)
        st.metric(
            "🎯 最高ヘッドショット",
            f"{best_headshots:,}",
            delta="1試合での記録"
        )
    
    with col4:
        match_wins = special_stats.get("match_wins", 0)
        st.metric(
            "🏆 マッチ勝利数",
            f"{match_wins:,}",
            delta=f"{match_wins/max(1, playtime_minutes/60):.2f} 勝利/h" if playtime_minutes > 0 else None
        )
    
    with col5:
        playtime_hours = playtime_minutes / 60
        st.metric(
            "⏰ 総プレイ時間",
            f"{playtime_hours:.1f}h",
            delta=f"{playtime_minutes:,} 分"
        )

def display_perk_overview(analysis):
    """改良されたPerk概要を表示する"""
    st.markdown("### 🎯 Perk詳細")
    
    perks = analysis.get("perks", {})
    
    if not perks:
        st.info("🔍 Perkデータが見つかりませんでした。")
        return
    
    # Perkカードの表示
    cols = st.columns(2)
    for i, (perk_name, data) in enumerate(sorted(perks.items(), key=lambda x: x[1]["level"], reverse=True)):
        col = cols[i % 2]
        
        with col:
            with st.container():
                # カードヘッダー
                icon = data.get("icon", "🎮")
                level = data["level"]
                progress = data["progress_percent"]
                
                # レベルによる色分け
                if level >= 25:
                    level_color = "🟢"
                elif level >= 20:
                    level_color = "🟡"
                elif level >= 15:
                    level_color = "🟠"
                else:
                    level_color = "🔴"
                
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1rem;
                    border-radius: 10px;
                    margin-bottom: 1rem;
                    color: white;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <h4 style="margin: 0; color: white;">{icon} {perk_name}</h4>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                        <span style="font-size: 1.2em; font-weight: bold;">{level_color} レベル {level}</span>
                        <span style="font-size: 0.9em;">XP: {data['xp']:,}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # プログレスバー
                if not data["is_max"]:
                    st.progress(progress / 100)
                    st.caption(f"次のレベルまで: {data['next_level_xp']:,} XP ({progress:.1f}%)")
                else:
                    st.progress(1.0)
                    st.caption("🎉 最大レベル到達！")
                
                # 特別な統計情報
                if perk_name == "Support" and "weld" in data:
                    st.caption(f"🔧 溶接ポイント: {data['weld_points']:,}")
                elif perk_name == "Field Medic" and "heal" in data:
                    st.caption(f"🏥 ヒールポイント: {data['heal_points']:,}")
    
    # Perkレベル分布グラフ
    st.markdown("#### 📈 Perkレベル分布")
    if len(perks) > 1:
        fig = go.Figure()
        
        # レベル別の色設定
        colors = ['#ff6b6b' if level < 15 else '#ffa500' if level < 20 else '#32cd32' if level < 25 else '#4169e1' 
                  for level in [perk["level"] for perk in perks.values()]]
        
        fig.add_trace(go.Bar(
            x=list(perks.keys()),
            y=[perk["level"] for perk in perks.values()],
            marker_color=colors,
            text=[f'Lv.{perk["level"]}' for perk in perks.values()],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>レベル: %{y}<br>XP: %{customdata:,}<extra></extra>',
            customdata=[perk["xp"] for perk in perks.values()]
        ))
        
        fig.update_layout(
            title="Perkレベル比較",
            xaxis_title="Perk",
            yaxis_title="レベル",
            yaxis=dict(range=[0, 27]),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)

def display_kill_statistics(analysis):
    """改良されたキル統計を表示する"""
    st.markdown("### 👹 キル統計")
    
    kills = analysis.get("kills", {})
    
    if not any(kills.values()):
        st.info("🔍 キルデータが見つかりませんでした。")
        return
    
    # キル統計のメトリクス表示
    col1, col2 = st.columns(2)
    
    # アクティブなキルデータのみ取得
    active_kills = {k: v for k, v in kills.items() if v > 0}
    
    for i, (kill_type, count) in enumerate(active_kills.items()):
        col = col1 if i % 2 == 0 else col2
        
        # エモジアイコンの設定
        if "総キル" in kill_type:
            icon = "💀"
        elif "ストーカー" in kill_type:
            icon = "👻"
        elif "クローラー" in kill_type:
            icon = "🕷️"
        elif "フレッシュパウンド" in kill_type:
            icon = "🧟"
        else:
            icon = "⚔️"
        
        with col:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
                padding: 1rem;
                border-radius: 10px;
                margin-bottom: 1rem;
                color: white;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <h3 style="margin: 0; color: white;">{icon}</h3>
                <p style="margin: 0; font-size: 1.2em; font-weight: bold;">{count:,}</p>
                <p style="margin: 0; font-size: 0.9em; opacity: 0.9;">{kill_type}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # キル分布の円グラフ
    if len(active_kills) > 1:
        st.markdown("#### 📊 キル分布")
        fig = px.pie(
            values=list(active_kills.values()),
            names=list(active_kills.keys()),
            title="",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)

def display_personal_bests(analysis):
    """改良されたパーソナルベスト表示"""
    st.markdown("### 🏆 パーソナルベスト")
    
    personal_bests = analysis.get("personal_bests", {})
    
    # アクティブなパーソナルベストのみ取得
    active_bests = {k: v for k, v in personal_bests.items() if v > 0}
    
    if not active_bests:
        st.info("🔍 パーソナルベストデータが見つかりませんでした。")
        return
    
    # 3列のレイアウト
    cols = st.columns(3)
    
    for i, (pb_name, value) in enumerate(sorted(active_bests.items(), key=lambda x: x[1], reverse=True)):
        col = cols[i % 3]
        
        # アイコンの設定
        if "ナイフ" in pb_name:
            icon = "🔪"
        elif "ピストル" in pb_name:
            icon = "🔫"
        elif "ヘッドショット" in pb_name:
            icon = "🎯"
        elif "ヒール" in pb_name:
            icon = "🏥"
        elif "キル" in pb_name:
            icon = "💀"
        elif "アシスト" in pb_name:
            icon = "🤝"
        elif "ZED" in pb_name:
            icon = "🧟"
        elif "DOSH" in pb_name:
            icon = "💰"
        else:
            icon = "⭐"
        
        with col:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #ffd700 0%, #ffb347 100%);
                padding: 1rem;
                border-radius: 10px;
                margin-bottom: 1rem;
                color: #333;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <h3 style="margin: 0; color: #333;">{icon}</h3>
                <p style="margin: 0; font-size: 1.4em; font-weight: bold; color: #333;">{value:,}</p>
                <p style="margin: 0; font-size: 0.9em; color: #666;">{pb_name}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # トップ記録のバーチャート
    if len(active_bests) > 1:
        st.markdown("#### 📈 記録比較")
        fig = px.bar(
            x=list(active_bests.keys()),
            y=list(active_bests.values()),
            title="",
            color=list(active_bests.values()),
            color_continuous_scale='Viridis'
        )
        fig.update_layout(
            xaxis_title="記録項目",
            yaxis_title="値",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

def display_achievement_progress(analysis, achievements_from_api, total_possible_achievements, achievements_schema):
    """改良された実績進捗表示"""
    st.markdown("### 🎖️ 実績進捗")

    # APIから取得した達成済み実績数
    achieved_count = len(achievements_from_api)
    total_ach = total_possible_achievements
    
    progress_percent = (achieved_count / total_ach * 100) if total_ach > 0 else 0

    # 実績の概要カード
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
    ">
        <h2 style="margin: 0; color: white;">🏆 実績達成状況</h2>
        <div style="margin: 1rem 0;">
            <span style="font-size: 3em; font-weight: bold;">{achieved_count}</span>
            <span style="font-size: 1.5em; margin-left: 0.5rem;">/ {total_ach}</span>
        </div>
        <div style="font-size: 1.2em; margin-top: 1rem;">
            達成率: {progress_percent:.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)

    # プログレスバー
    st.progress(progress_percent / 100)

    # 達成済み実績の一覧表示
    with st.expander("🏆 達成済み実績一覧", expanded=False): 
        if not achievements_from_api:
            st.info("🔍 達成済みの実績はありません。")
        else:
            # 実績を3列で表示
            cols = st.columns(3)
            for i, ach in enumerate(achievements_from_api):
                col = cols[i % 3]
                api_name = ach.get("name")
                schema_info = achievements_schema.get(api_name, {})
                display_name = schema_info.get("displayName", api_name)
                description = schema_info.get("description", "")
                
                with col:
                    st.markdown(f"""
                    <div style="
                        background: #f8f9fa;
                        padding: 1rem;
                        border-radius: 8px;
                        margin-bottom: 1rem;
                        border-left: 4px solid #28a745;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    ">
                        <h5 style="margin: 0; color: #333;">🏆 {display_name}</h5>
                        <p style="margin: 0.5rem 0 0 0; font-size: 0.85em; color: #666;">{description}</p>
                    </div>
                    """, unsafe_allow_html=True)

def display_special_stats(analysis):
    """改良された特別統計表示"""
    st.markdown("### 🌟 特別統計")
    
    special_stats = analysis.get("special_stats", {})
    
    # 統計カードの表示
    stats_items = [
        ("🏆", "マッチ勝利数", special_stats.get('match_wins', 0)),
        ("🎉", "スペシャルイベント", special_stats.get('special_event_progress', 0)),
        ("📅", "ウィークリーイベント", special_stats.get('weekly_event_progress', 0)),
        ("📊", "デイリーイベント", special_stats.get('daily_event_info', 0)),
        ("💰", "DOSH Vault合計", special_stats.get('dosh_vault_total', 0)),
        ("💎", "DOSH Vault進捗", special_stats.get('dosh_vault_progress', 0)),
    ]
    
    cols = st.columns(3)
    for i, (icon, label, value) in enumerate(stats_items):
        col = cols[i % 3]
        
        with col:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1.5rem;
                border-radius: 10px;
                margin-bottom: 1rem;
                color: white;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <h3 style="margin: 0; color: white;">{icon}</h3>
                <p style="margin: 0; font-size: 1.4em; font-weight: bold;">{value:,}</p>
                <p style="margin: 0; font-size: 0.9em; opacity: 0.9;">{label}</p>
            </div>
            """, unsafe_allow_html=True)

# --- サイドバーとメインロジック (test4.pyから移動) ---

def render_sidebar():
    """サイドバーの入力欄とヘルプテキストを表示する"""
    st.sidebar.header("🔧 設定")
    api_key = st.sidebar.text_input("Steam APIキー", type="password", help="Steamから発行されたWeb APIキーを入力します。")
    steam_id = st.sidebar.text_input("64ビットSteam ID", help="あなたのSteamプロフィールの固有IDです。")
    selected_game = st.sidebar.selectbox("ゲームを選択", list(GAME_APP_IDS.keys()))
    
    show_debug = st.sidebar.checkbox("デバッグ情報を表示", value=False)

    st.sidebar.markdown("---")
    st.sidebar.info(
        """
        **APIキーの取得方法:**
        1. [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) にアクセス
        2. ログインしてキーを登録

        **64ビットSteam IDの調べ方:**
        1. ご自身のSteamプロフィールページを開く
        2. ページのURLをコピー
        3. [steamid.io](https://steamid.io) 等のサイトでURLを検索し、`steamID64` を確認
        """
    )
    return api_key, steam_id, selected_game, show_debug

# --- Main App Logic ---

st.set_page_config(page_title="Enhanced KF2 Stats Viewer", layout="wide")
st.title("🎮 Killing Floor 2 Stats Viewer")

api_key, steam_id, selected_game, show_debug = render_sidebar()

if st.sidebar.button("📊 戦績を表示", type="primary"):
    if not api_key or not steam_id:
        st.sidebar.error("APIキーとSteam IDの両方を入力してください。")
    else:
        app_id = GAME_APP_IDS[selected_game]
        
        try:
            with st.spinner(f"**{selected_game}** の戦績データを取得中..."):
                player_stats = get_player_stats(api_key, steam_id, app_id)
                playtime_minutes = get_player_playtime(api_key, steam_id, app_id)
                total_possible_achievements = get_total_achievements(api_key, app_id)
                schema_data = get_game_schema(api_key, app_id)
                schema_dict = schema_data.get("stats", {})
                achievements_schema = schema_data.get("achievements", {})
                
            if player_stats and "stats" in player_stats:
                # st.header(f"📊 {selected_game} 詳細ダッシュボード")
                # st.caption(f"SteamID: {steam_id} | 総プレイ時間: {playtime_minutes/60:.1f}時間")
                
                # 統計データの処理
                stats_dict = {s['name']: s['value'] for s in player_stats["stats"]}
                achievements_from_api = player_stats.get("achievements", [])
                
                # データ分析
                analysis = analyze_kf2_stats(stats_dict)
                
                # タブで情報を整理
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "🎯 Perk情報", "👹 キル統計", "🏆 パーソナルベスト",
                    "🎖️ 実績進捗", "🌟 特別統計"
                ])
                
                with tab1:
                    display_perk_overview(analysis)
                
                with tab2:
                    display_kill_statistics(analysis)
                
                with tab3:
                    display_personal_bests(analysis)
                
                with tab4:
                    display_achievement_progress(analysis, achievements_from_api, total_possible_achievements, achievements_schema)
                
                with tab5:
                    display_special_stats(analysis)
                
                # デバッグ情報表示
                if show_debug:
                    display_debug_info(stats_dict, schema_dict)
         
            else:
                st.error("戦績データを取得できませんでした。以下の点をご確認ください:\n"
                         "- Steam IDとAPIキーが正しいか\n"
                         "- Steamプロフィールのプライバシー設定で「ゲームの詳細」が「公開」になっているか\n"
                         "- 対象ゲームをプレイしたことがあるか")

        except Exception as e:
            st.error(f"予期せぬエラーが発生しました: {e}")
            st.error("詳細なエラー情報については、デバッグモードを有効にしてもう一度お試しください。")

# フッター
st.markdown("---")
st.markdown("*Enhanced KF2 Stats Viewer - より詳細な統計情報を提供します*")