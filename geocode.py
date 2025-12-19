#!/usr/bin/env python3
"""
ランドマークの緯度経度を取得するスクリプト（SerpAPI使用）
"""

import re
import sys

import requests

from config import load_api_key as _load_api_key


def load_api_key() -> str:
    """SerpAPI用のAPIキーを読み込む"""
    key = _load_api_key("serpapi")
    if key is None:
        raise FileNotFoundError("SerpAPI APIキーが見つかりません")
    return key


def get_account_info() -> dict | None:
    """
    SerpApiのアカウント情報を取得

    Returns:
        {"plan_searches_left": int, "searches_per_month": int} or None
    """
    try:
        api_key = load_api_key()
        resp = requests.get(
            "https://serpapi.com/account",
            params={"api_key": api_key},
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        result = {
            "plan_searches_left": data.get("plan_searches_left", 0),
            "searches_per_month": data.get("searches_per_month", 100),
        }
        print(f"SerpApi account info: {result}")
        return result
    except Exception as e:
        print(f"SerpApi account info取得エラー: {e}")
        return None


def get_coordinates(landmark: str) -> dict | None:
    """
    ランドマーク名から緯度経度を取得

    Returns:
        {"name": str, "lat": float, "lng": float} or None
    """
    api_key = load_api_key()

    # Google Mapsの検索を使用（local_resultsから座標を取得）
    params = {
        "q": landmark,
        "hl": "ja",
        "gl": "jp",
        "api_key": api_key,
    }

    print(f"SerpAPI検索クエリ: {landmark}")
    resp = requests.get("https://serpapi.com/search", params=params)
    resp.raise_for_status()
    data = resp.json()

    # 1. Knowledge Graph から座標を取得（最も信頼性が高い）
    knowledge_graph = data.get("knowledge_graph", {})
    if knowledge_graph:
        # GPS座標が直接含まれている場合
        gps = knowledge_graph.get("gps_coordinates", {})
        if gps:
            lat = gps.get("latitude")
            lng = gps.get("longitude")
            if lat and lng:
                print(f"Knowledge Graph GPS: {lat}, {lng}")
                return {"name": landmark, "lat": lat, "lng": lng}

        # 「位置」フィールドから座標を抽出（山や地形など）
        location_text = knowledge_graph.get("位置", "")
        if location_text:
            # 小数点付き度数形式を優先的に抽出 (例: 北緯35.3606度 東経138.7275度)
            decimal_pattern = r"北緯(\d+\.\d+)度.*?東経(\d+\.\d+)度"
            match = re.search(decimal_pattern, location_text)
            if match:
                lat = float(match.group(1))
                lng = float(match.group(2))
                print(f"Knowledge Graph 位置フィールド (小数): {lat}, {lng}")
                return {"name": landmark, "lat": lat, "lng": lng}

            # DMS形式を抽出して変換 (例: 北緯35度21分38秒 東経138度43分39秒)
            dms_pattern = r"北緯(\d+)度(\d+)分([\d.]+)秒.*?東経(\d+)度(\d+)分([\d.]+)秒"
            match = re.search(dms_pattern, location_text)
            if match:
                lat = float(match.group(1)) + float(match.group(2)) / 60 + float(match.group(3)) / 3600
                lng = float(match.group(4)) + float(match.group(5)) / 60 + float(match.group(6)) / 3600
                print(f"Knowledge Graph 位置フィールド (DMS): {lat:.6f}, {lng:.6f}")
                return {"name": landmark, "lat": round(lat, 6), "lng": round(lng, 6)}

        # ヘッダー情報に座標がある場合
        header = knowledge_graph.get("header_images", [])
        for img in header:
            if "gps_coordinates" in img:
                gps = img["gps_coordinates"]
                lat = gps.get("latitude")
                lng = gps.get("longitude")
                if lat and lng:
                    print(f"Knowledge Graph Header GPS: {lat}, {lng}")
                    return {"name": landmark, "lat": lat, "lng": lng}

    # 2. Local Results から座標を取得（地図検索結果）
    local_results = data.get("local_results", {})
    places = local_results.get("places", [])
    if places:
        place = places[0]
        gps = place.get("gps_coordinates", {})
        lat = gps.get("latitude")
        lng = gps.get("longitude")
        if lat and lng:
            print(f"Local Results GPS: {lat}, {lng}")
            return {"name": place.get("title", landmark), "lat": lat, "lng": lng}

    # 3. AI概要からテキスト抽出を試みる
    ai_overview = data.get("ai_overview", {})
    text_blocks = ai_overview.get("text_blocks", [])
    text = " ".join(block.get("snippet", "") for block in text_blocks)

    # AI概要がない場合、検索結果のスニペットから探す
    if not text:
        organic = data.get("organic_results", [])
        text = " ".join(r.get("snippet", "") for r in organic[:5])

    if text:
        print(f"テキストから座標抽出を試行: {text[:100]}...")

        # 度数形式を抽出 (例: 35.4550426, 139.6312741)
        match = re.search(r"(\d{1,2}\.\d{4,})[,\s、]+(\d{2,3}\.\d{4,})", text)
        if match:
            result = {
                "name": landmark,
                "lat": float(match.group(1)),
                "lng": float(match.group(2)),
            }
            print(f"度数形式で抽出: {result}")
            return result

        # DMS形式からの変換を試みる (例: 北緯35度27分16.53秒)
        dms_pattern = r"[北南]緯(\d+)度(\d+)分([\d.]+)秒.*?[東西]経(\d+)度(\d+)分([\d.]+)秒"
        match = re.search(dms_pattern, text)
        if match:
            lat = float(match.group(1)) + float(match.group(2)) / 60 + float(match.group(3)) / 3600
            lng = float(match.group(4)) + float(match.group(5)) / 60 + float(match.group(6)) / 3600
            result = {
                "name": landmark,
                "lat": round(lat, 7),
                "lng": round(lng, 7),
            }
            print(f"DMS形式で抽出: {result}")
            return result

    # 4. Google Maps検索をフォールバックとして試行
    print(f"通常検索で見つからず、Google Maps検索を試行: {landmark}")
    try:
        maps_params = {
            "q": landmark,
            "engine": "google_maps",
            "type": "search",
            "hl": "ja",
            "gl": "jp",
            "api_key": api_key,
        }
        maps_resp = requests.get("https://serpapi.com/search", params=maps_params, timeout=10)
        maps_resp.raise_for_status()
        maps_data = maps_resp.json()

        # local_resultsから座標を取得
        local_results = maps_data.get("local_results", [])
        if local_results:
            place = local_results[0]
            gps = place.get("gps_coordinates", {})
            lat = gps.get("latitude")
            lng = gps.get("longitude")
            if lat and lng:
                print(f"Google Maps検索結果: {lat}, {lng}")
                return {"name": place.get("title", landmark), "lat": lat, "lng": lng}

        # place_resultsから座標を取得
        place_results = maps_data.get("place_results", {})
        gps = place_results.get("gps_coordinates", {})
        lat = gps.get("latitude")
        lng = gps.get("longitude")
        if lat and lng:
            print(f"Google Maps place_results: {lat}, {lng}")
            return {"name": place_results.get("title", landmark), "lat": lat, "lng": lng}

    except Exception as e:
        print(f"Google Maps検索エラー: {e}")

    print(f"座標が見つかりませんでした: {landmark}")
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: geocode.py <landmark name>", file=sys.stderr)
        sys.exit(1)
    
    landmark = " ".join(sys.argv[1:])
    
    try:
        result = get_coordinates(landmark)
        if result:
            print(f"{result['lat']},{result['lng']}")
        else:
            print(f"座標が見つかりませんでした: {landmark}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()