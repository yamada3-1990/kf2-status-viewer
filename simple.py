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
    "Commando": {"progress": 1, "build": 2},
    "Berserker": {"progress": 10, "build": 11},
    "Support": {"progress": 20, "build": 21, "weld": 22},
    "Firebug": {"progress": 30, "build": 31},
    "Field Medic": {"progress": 40, "build": 41, "heal": 42},
    "Sharpshooter": {"progress": 50, "build": 51},
    "Demolitionist": {"progress": 60, "build": 61},
    "Survivalist": {"progress": 70, "build": 71},
    "Gunslinger": {"progress": 80, "build": 81},
    "SWAT": {"progress": 90, "build": 91},
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

# コレクティブル実績
# COLLECTIBLE_ACHIEVEMENTS = {
#     "Catacombs": 4021,
#     "Biotics": 4022,
#     "Evacuation Point": 4023,
#     "Outpost": 4024,
#     "Prison": 4025,
#     "Manor": 4026,
#     "Paris": 4027,
#     "Farmhouse": 4028,
#     "Black Forest": 4029,
#     "Containment Station": 4030,
#     "Infernal Realm": 4031,
#     "Hostile Grounds": 4032,
#     "Zed Landing": 4035,
#     "Descent": 4036,
#     "Nuked": 4037,
#     "Tragic Kingdom": 4038,
#     "Nightmare": 4039,
#     "Krampus": 4040,
#     "Arena": 4041,
#     "Powercore": 4042,
#     "Airship": 4043,
#     "Lockdown": 4044,
#     "Monster Ball": 4045,
#     "Monster Ball Secret": 4046,
# }

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
                "is_max": level >= MAX_PERK_LEVEL
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
    
    # コレクティブル実績
    # collectibles = {}
    # for map_name, stat_id in COLLECTIBLE_ACHIEVEMENTS.items():
    #     collectibles[map_name] = get_stat_value(stats_dict, stat_id)
    # analysis["collectibles"] = collectibles
    
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

def display_perk_overview(analysis):
    """Perk概要を表示する"""
    st.subheader("🎯 Perk概要")
    
    perks = analysis.get("perks", {})
    
    if not perks:
        st.info("Perkデータが見つかりませんでした。")
        return
    
    # 全Perkの統計
    total_perks = len(perks)
    max_level_perks = sum(1 for perk in perks.values() if perk["is_max"])
    total_xp = sum(perk["xp"] for perk in perks.values())
    avg_level = sum(perk["level"] for perk in perks.values()) / total_perks if total_perks > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("総Perk数", total_perks)
    col2.metric("MAX Perk", f"{max_level_perks}/{total_perks}")
    col3.metric("総経験値", f"{total_xp:,}")
    col4.metric("平均レベル", f"{avg_level:.1f}")
    
    # Perkレベルの詳細表示
    st.subheader("📊 Perkレベル詳細")
    
    perk_data = []
    for perk_name, data in perks.items():
        perk_data.append({
            "Perk": perk_name,
            "Level": data["level"],
            "Progress": f"{data['progress_percent']:.1f}%",
            "XP": f"{data['xp']:,}",
            "Next Level": f"{data['next_level_xp']:,}" if not data["is_max"] else "MAX"
            # "Special": ""
        })
        
        # 特別な統計情報を追加
        # if perk_name == "Support" and "weld_points" in data:
        #     perk_data[-1]["Special"] = f"溶接: {data['weld_points']}"
        # elif perk_name == "Field Medic" and "heal_points" in data:
        #     perk_data[-1]["Special"] = f"ヒール: {data['heal_points']}"
    
    # レベルでソート
    perk_df = pd.DataFrame(perk_data).sort_values(by="Level", ascending=False)
    st.dataframe(perk_df, use_container_width=True, hide_index=True)
    
    # Perkレベル分布のグラフ
    if len(perks) > 1:
        fig = px.bar(
            x=list(perks.keys()),
            y=[perk["level"] for perk in perks.values()],
            title="Perkレベル分布",
            labels={"x": "Perk", "y": "Level"}
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

def display_kill_statistics(analysis):
    """キル統計を表示する"""
    st.subheader("👹 キル統計")
    
    kills = analysis.get("kills", {})
    
    if not any(kills.values()):
        st.info("キルデータが見つかりませんでした。")
        return
    
    # キル統計の表示
    col1, col2 = st.columns(2)
    
    for i, (kill_type, count) in enumerate(kills.items()):
        if count > 0:
            if i % 2 == 0:
                col1.metric(kill_type, f"{count:,}")
            else:
                col2.metric(kill_type, f"{count:,}")
    
    # キル分布のグラフ
    active_kills = {k: v for k, v in kills.items() if v > 0}
    if len(active_kills) > 1:
        fig = px.pie(
            values=list(active_kills.values()),
            names=list(active_kills.keys()),
            title="キル分布"
        )
        st.plotly_chart(fig, use_container_width=True)

def display_personal_bests(analysis):
    """パーソナルベストを表示する"""
    st.subheader("🏆 パーソナルベスト")
    
    personal_bests = analysis.get("personal_bests", {})
    
    if not any(personal_bests.values()):
        st.info("パーソナルベストデータが見つかりませんでした。")
        return
    
    # パーソナルベストの表示
    pb_data = []
    for pb_name, value in personal_bests.items():
        if value > 0:
            pb_data.append({
                "記録": pb_name,
                "値": f"{value:,}"
            })
    
    if pb_data:
        pb_df = pd.DataFrame(pb_data).sort_values(by="値", ascending=False)
        st.dataframe(pb_df, use_container_width=True, hide_index=True)
        
        # トップパフォーマンスのグラフ
        if len(pb_data) > 1:
            fig = px.bar(
                x=[item["記録"] for item in pb_data],
                y=[int(item["値"].replace(",", "")) for item in pb_data],
                title="パーソナルベスト比較"
            )
            st.plotly_chart(fig, use_container_width=True)

def display_achievement_progress(analysis, achievements_from_api, total_possible_achievements, achievements_schema):
    """実績進捗と達成済み実績リストを表示する"""
    st.subheader("🎖️ 実績進捗")

    # APIから取得した達成済み実績数
    achieved_count = len(achievements_from_api)
    total_ach = total_possible_achievements
    
    progress_percent = (achieved_count / total_ach * 100) if total_ach > 0 else 0

    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.progress(progress_percent / 100)
        st.caption(f"達成率: {progress_percent:.2f}%")
    with col2:
        st.metric("実績達成数", f"{achieved_count} / {total_ach}")

    # 達成済み実績の一覧表示
    with st.expander("達成済み実績の一覧を表示する"): 
        if not achievements_from_api:
            st.info("達成済みの実績はありません。")
        else:
            ach_list_data = []
            # APIから取得した実績リストをループ
            for ach in achievements_from_api:
                api_name = ach.get("name")
                # スキーマ情報から表示名や説明文を取得
                schema_info = achievements_schema.get(api_name, {})
                display_name = schema_info.get("displayName", api_name) # 見つからなければAPI名をそのまま使う
                description = schema_info.get("description", "-")
                
                ach_list_data.append({
                    "実績名": display_name,
                    "内容": description
                })
            
            df = pd.DataFrame(ach_list_data)
            st.dataframe(df, use_container_width=True, hide_index=True, height=300)

    # 統計データから取得した実績情報（参考）
    achievements_from_stats = analysis.get("achievements", {})
    if any(achievements_from_stats.values()):
        with st.expander("統計情報に基づく実績の進捗（開発者向け参考情報）"):
            ach_data = []
            for ach_name, value in achievements_from_stats.items():
                if value > 0:
                    ach_data.append({
                        "実績項目 (統計より)": ach_name,
                        "進捗/値": f"{value:,}"
                    })
            if ach_data:
                ach_df = pd.DataFrame(ach_data)
                st.dataframe(ach_df, use_container_width=True, hide_index=True)

# def display_collectibles(analysis):
#     """コレクティブル実績を表示する"""
#     st.subheader("💎 コレクティブル実績")
    
#     collectibles = analysis.get("collectibles", {})
    
#     if not any(collectibles.values()):
#         st.info("コレクティブルデータが見つかりませんでした。")
#         return
    
#     # コレクティブルの表示
#     col_data = []
#     for map_name, value in collectibles.items():
#         if value > 0:
#             col_data.append({
#                 "マップ": map_name,
#                 "収集数": f"{value:,}"
#             })
    
#     if col_data:
#         col_df = pd.DataFrame(col_data).sort_values(by="収集数", ascending=False)
#         st.dataframe(col_df, use_container_width=True, hide_index=True)

def display_special_stats(analysis):
    """特別な統計を表示する"""
    st.subheader("🌟 特別な統計")
    
    special_stats = analysis.get("special_stats", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("マッチ勝利数", f"{special_stats.get('match_wins', 0):,}")
        st.metric("スペシャルイベント進捗", f"{special_stats.get('special_event_progress', 0):,}")
    
    with col2:
        st.metric("ウィークリーイベント進捗", f"{special_stats.get('weekly_event_progress', 0):,}")
        st.metric("デイリーイベント情報", f"{special_stats.get('daily_event_info', 0):,}")
    
    with col3:
        st.metric("DOSH Vault合計", f"{special_stats.get('dosh_vault_total', 0):,}")
        st.metric("DOSH Vault進捗", f"{special_stats.get('dosh_vault_progress', 0):,}")

def display_debug_info(stats_dict, schema_dict):
    """デバッグ情報を表示する"""
    with st.expander("🔍 デバッグ情報 (開発用)", expanded=False):
        st.subheader("取得された統計データ")
        
        # 統計データをDataFrameで表示
        debug_data = []
        for name, value in stats_dict.items():
            schema_name = schema_dict.get(name, "スキーマなし")
            
            debug_data.append({
                "統計名": name,
                "スキーマ表示名": schema_name,
                "値": f"{value:,}"
            })
        
        # 値でソート（降順）
        df = pd.DataFrame(debug_data).sort_values(by="統計名")
        st.dataframe(df, use_container_width=True, height=400)
        
        # 統計の要約
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("総統計数", len(stats_dict))
        with col2:
            non_zero_stats = sum(1 for value in stats_dict.values() if value > 0)
            st.metric("非ゼロ統計数", non_zero_stats)
        with col3:
            st.metric("ゼロ統計数", len(stats_dict) - non_zero_stats)

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

st.set_page_config(page_title="KF2 Stats Viewer", layout="wide")
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
                
                # with tab5:
                #     display_collectibles(analysis)
                
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
st.markdown("KF2 Stats Viewer")