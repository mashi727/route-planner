"""ルートファイルの入出力パーサ（Qt非依存）。

GPX / KML / KMZ のパースと、ルート（waypoints）の JSON 読み書き。
ファイル選択ダイアログやエラー表示は UI 側の責務で、ここは純粋な
パース/シリアライズのみを行う。TrackPoint/Waypoint は素の dict で表す:

    TrackPoint: {"lat": float, "lon": float, "ele": float | None}
    Waypoint  : {"lat": float, "lon": float, "ele": float | None, "name": str | None}
"""

import json
import zipfile
import xml.etree.ElementTree as ET


GPX_NS = "http://www.topografix.com/GPX/1/1"
KML_NS = "http://www.opengis.net/kml/2.2"


def parse_gpx(path) -> list:
    """GPX ファイルからトラックポイント列を抽出する。

    Returns:
        ``[{"lat", "lon", "ele"}, ...]``（トラックポイントが無ければ空リスト）
    """
    tree = ET.parse(path)
    root = tree.getroot()

    # GPX名前空間を取得
    ns = {"gpx": GPX_NS}
    if root.tag.startswith("{"):
        ns_uri = root.tag.split("}")[0] + "}"
        ns = {"gpx": ns_uri[1:-1]}

    track_points = []

    # trk/trkseg/trkpt を探す
    for trkpt in root.findall(".//gpx:trkpt", ns):
        lat = float(trkpt.get("lat"))
        lon = float(trkpt.get("lon"))
        ele_elem = trkpt.find("gpx:ele", ns)
        ele = float(ele_elem.text) if ele_elem is not None else None
        track_points.append({"lat": lat, "lon": lon, "ele": ele})

    # 名前空間なしでも試す
    if not track_points:
        for trkpt in root.findall(".//trkpt"):
            lat = float(trkpt.get("lat"))
            lon = float(trkpt.get("lon"))
            ele_elem = trkpt.find("ele")
            ele = float(ele_elem.text) if ele_elem is not None else None
            track_points.append({"lat": lat, "lon": lon, "ele": ele})

    return track_points


def parse_kml_kmz(path):
    """KML / KMZ ファイルからルートと経由地を抽出する。

    Returns:
        ``(track_points, waypoints)`` のタプル。
        - track_points: ``[{"lat", "lon", "ele"}, ...]``
        - waypoints: ``[{"lat", "lon", "ele", "name"}, ...]``（Placemark/Point）

        LineString が無く Point のみの場合、track_points は経由地から生成する。
    """
    path_str = str(path)

    # KMZかKMLかを判定
    if path_str.lower().endswith(".kmz"):
        # KMZはZIPファイル、中の doc.kml（無ければ最初の*.kml）を読み込む
        with zipfile.ZipFile(path_str, "r") as zf:
            kml_files = [f for f in zf.namelist() if f.endswith(".kml")]
            if not kml_files:
                raise ValueError("KMZファイル内にKMLが見つかりません")
            kml_name = "doc.kml" if "doc.kml" in kml_files else kml_files[0]
            with zf.open(kml_name) as kml_file:
                root = ET.fromstring(kml_file.read())
    else:
        tree = ET.parse(path_str)
        root = tree.getroot()

    # KML名前空間を取得
    ns = {"kml": KML_NS}
    if root.tag.startswith("{"):
        ns_uri = root.tag.split("}")[0] + "}"
        ns = {"kml": ns_uri[1:-1]}

    track_points = []
    waypoints = []

    # Placemarkを探す
    placemarks = root.findall(".//kml:Placemark", ns)
    if not placemarks:
        placemarks = root.findall(".//Placemark")

    for placemark in placemarks:
        # 名前を取得
        name_elem = placemark.find("kml:name", ns)
        if name_elem is None:
            name_elem = placemark.find("name")
        name = name_elem.text if name_elem is not None else None

        # LineString（ルート）を探す
        linestring = placemark.find(".//kml:LineString", ns)
        if linestring is None:
            linestring = placemark.find(".//LineString")

        if linestring is not None:
            coords_elem = linestring.find("kml:coordinates", ns)
            if coords_elem is None:
                coords_elem = linestring.find("coordinates")
            if coords_elem is not None and coords_elem.text:
                coords_text = coords_elem.text.strip()
                for coord in coords_text.split():
                    parts = coord.split(",")
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        ele = float(parts[2]) if len(parts) >= 3 else None
                        track_points.append({"lat": lat, "lon": lon, "ele": ele})

        # Point（経由地）を探す
        point = placemark.find(".//kml:Point", ns)
        if point is None:
            point = placemark.find(".//Point")

        if point is not None:
            coords_elem = point.find("kml:coordinates", ns)
            if coords_elem is None:
                coords_elem = point.find("coordinates")
            if coords_elem is not None and coords_elem.text:
                parts = coords_elem.text.strip().split(",")
                if len(parts) >= 2:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    ele = float(parts[2]) if len(parts) >= 3 else None
                    waypoints.append({"lat": lat, "lon": lon, "ele": ele, "name": name})

    # ルートがない場合は経由地から作成
    if not track_points and waypoints:
        track_points = [
            {"lat": wp["lat"], "lon": wp["lon"], "ele": wp.get("ele")} for wp in waypoints
        ]

    return track_points, waypoints


def load_waypoints_json(path) -> list:
    """ルート JSON を読み込み、waypoint 辞書のリストを返す。

    Returns:
        ``[{"lat", "lng", "name"}, ...]``（"waypoints" キーの内容）
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("waypoints", [])


def save_waypoints_json(path, waypoints) -> None:
    """``[(lat, lng, name), ...]`` を JSON に保存する。"""
    data = {
        "waypoints": [
            {"lat": lat, "lng": lng, "name": name} for lat, lng, name in waypoints
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
