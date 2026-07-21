"""io_formats モジュールの単体テスト。"""

import zipfile

import pytest

from route_planner import io_formats


GPX_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="35.0" lon="139.0"><ele>10.0</ele></trkpt>
    <trkpt lat="35.1" lon="139.1"><ele>20.0</ele></trkpt>
    <trkpt lat="35.2" lon="139.2"><ele>30.0</ele></trkpt>
  </trkseg></trk>
</gpx>
"""

KML_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Placemark><name>ルート</name>
    <LineString><coordinates>
      139.0,35.0,10 139.1,35.1,20 139.2,35.2,30
    </coordinates></LineString>
  </Placemark>
  <Placemark><name>スタート地点</name>
    <Point><coordinates>139.0,35.0,10</coordinates></Point>
  </Placemark>
</Document></kml>
"""


def test_parse_gpx(tmp_path):
    p = tmp_path / "sample.gpx"
    p.write_text(GPX_SAMPLE, encoding="utf-8")
    pts = io_formats.parse_gpx(p)
    assert len(pts) == 3
    assert pts[0] == {"lat": 35.0, "lon": 139.0, "ele": 10.0}
    assert pts[2]["ele"] == 30.0


def test_parse_gpx_no_elevation(tmp_path):
    gpx = GPX_SAMPLE.replace("<ele>10.0</ele>", "").replace("<ele>20.0</ele>", "").replace("<ele>30.0</ele>", "")
    p = tmp_path / "noele.gpx"
    p.write_text(gpx, encoding="utf-8")
    pts = io_formats.parse_gpx(p)
    assert len(pts) == 3
    assert all(pt["ele"] is None for pt in pts)


def test_parse_kml(tmp_path):
    p = tmp_path / "sample.kml"
    p.write_text(KML_SAMPLE, encoding="utf-8")
    track_points, waypoints = io_formats.parse_kml_kmz(p)
    assert len(track_points) == 3
    assert track_points[0]["lat"] == 35.0
    assert track_points[0]["lon"] == 139.0
    # Point の Placemark が経由地として抽出される
    assert len(waypoints) == 1
    assert waypoints[0]["name"] == "スタート地点"


def test_parse_kmz(tmp_path):
    kmz = tmp_path / "sample.kmz"
    with zipfile.ZipFile(kmz, "w") as zf:
        zf.writestr("doc.kml", KML_SAMPLE)
    track_points, waypoints = io_formats.parse_kml_kmz(kmz)
    assert len(track_points) == 3
    assert len(waypoints) == 1


def test_parse_kmz_without_kml_raises(tmp_path):
    kmz = tmp_path / "empty.kmz"
    with zipfile.ZipFile(kmz, "w") as zf:
        zf.writestr("readme.txt", "no kml here")
    with pytest.raises(ValueError):
        io_formats.parse_kml_kmz(kmz)


def test_waypoints_json_roundtrip(tmp_path):
    p = tmp_path / "route.json"
    waypoints = [
        (35.0, 139.0, "スタート"),
        (35.5, 139.5, "経由1"),
        (36.0, 140.0, "ゴール"),
    ]
    io_formats.save_waypoints_json(p, waypoints)
    loaded = io_formats.load_waypoints_json(p)
    assert loaded == [
        {"lat": 35.0, "lng": 139.0, "name": "スタート"},
        {"lat": 35.5, "lng": 139.5, "name": "経由1"},
        {"lat": 36.0, "lng": 140.0, "name": "ゴール"},
    ]
