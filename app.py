import os
import re
import json
import math
import networkx as nx
import pandas as pd
import streamlit as st
import folium
from folium import DivIcon
from folium.plugins import LocateControl, AntPath
from streamlit_folium import st_folium
import streamlit.components.v1 as components
from PIL import Image

# 1. Cấu hình trang
st.set_page_config(
    page_title="Make by BangNC13",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject CSS Streamlit
st.markdown("""
    <style>
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 999999 !important;
        pointer-events: none;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    button[data-testid="stHeaderIconButton"],
    [data-testid="stSidebarCollapseButton"] button {
        pointer-events: auto !important;
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
        z-index: 1000000 !important;
        background-color: #FFEDD5 !important;
        color: #EA580C !important;
        border-radius: 50% !important;
        width: 40px !important;
        height: 40px !important;
        padding: 0px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border: 2px solid #FF5F1F !important;
        box-shadow: 0 0 10px rgba(255, 95, 31, 0.5), 0 4px 12px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.2s ease-in-out !important;
    }

    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        max-width: 100% !important;
    }

    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.15) !important;
        backdrop-filter: blur(18px) saturate(180%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.3) !important;
        z-index: 999998 !important;
    }
    </style>
""", unsafe_allow_html=True)

def normalize_node(node_str):
    if pd.isna(node_str):
        return ""
    s = str(node_str).strip()
    s = re.sub(r'/\d+$', '', s)
    match = re.match(r'([A-Za-z0-9]+)\.(\d+)/([A-Za-z0-9]+)', s)
    if match:
        prefix, num, suffix = match.groups()
        return f"{prefix}.{int(num):04d}/{suffix}"
    return s

def apply_map_custom_css(folium_map):
    font_awesome_link = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
    folium_map.get_root().html.add_child(folium.Element(font_awesome_link))
    custom_css = """
    <style>
    .leaflet-control-zoom { display: none !important; }
    .leaflet-control-locate { margin-top: 70px !important; margin-left: 10px !important; }
    .leaflet-control-layers { margin-top: 70px !important; margin-right: 10px !important; }
    </style>
    """
    folium_map.get_root().html.add_child(folium.Element(custom_css))

# 3. Tải dữ liệu Excel & JSON API đặc thù
@st.cache_data
def load_data():
    file_path = "Data.xlsx"
    df_uplink = pd.read_excel(file_path, sheet_name="uplink")
    df_cable = pd.read_excel(file_path, sheet_name="Đoạn cáp")
    df_hdn = pd.read_excel(file_path, sheet_name="HĐN")
    return df_uplink, df_cable, df_hdn

@st.cache_data
def load_json_api_objects(json_file_path="TQGP001.json"):
    """
    Parse cấu trúc file JSON dạng API string bị escape để lấy danh sách điểm/tập điểm
    """
    node_coords = {}
    cable_shapes = {}

    if not os.path.exists(json_file_path):
        return node_coords, cable_shapes

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Xử lý chuỗi JSON lồng nhau (Stringify)
        results_str = raw_data.get("results", "")
        if isinstance(results_str, str):
            table_dict = json.loads(results_str)
            inner_table_str = table_dict.get("Table", "")
            if isinstance(inner_table_str, str):
                final_dict = json.loads(inner_table_str)
                object_list = final_dict.get("responseResult", {}).get("result", {}).get("objectInfo", [])
                
                for obj in object_list:
                    name = normalize_node(obj.get("name"))
                    latlng_str = obj.get("latLng", "")
                    # Tách tọa độ dạng "(21.7992374,105.2110277)"
                    match = re.search(r'\(([-+]?\d*\.\d+|\d+),\s*([-+]?\d*\.\d+|\d+)\)', latlng_str)
                    if match and name:
                        lat, lng = float(match.group(1)), float(match.group(2))
                        node_coords[name] = (lat, lng)

        # Nếu file JSON chứa thêm mảng GeoJSON LineString tiêu chuẩn
        if isinstance(raw_data, dict) and raw_data.get("type") == "FeatureCollection":
            for feature in raw_data.get("features", []):
                props = feature.get("properties", {})
                cable_name = props.get("name") or props.get("TEN_DOAN_CAP")
                geom = feature.get("geometry", {})
                if geom.get("type") == "LineString":
                    cable_shapes[str(cable_name).strip()] = [[p[1], p[0]] for p in geom.get("coordinates", [])]

    except Exception as e:
        st.error(f"Lỗi khi parse file {json_file_path}: {e}")

    return node_coords, cable_shapes

try:
    df_uplink, df_cable, df_hdn = load_data()
    json_nodes, json_cable_shapes = load_json_api_objects("TQGP001.json")
except Exception as e:
    st.error(f"Lỗi khi tải dữ liệu: {e}")
    st.stop()

# 4. Trích xuất tọa độ HĐN (Kết hợp Excel + JSON để tăng độ chính xác)
df_hdn['Lat_clean'] = pd.to_numeric(df_hdn['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
df_hdn['Lng_clean'] = pd.to_numeric(df_hdn['Lng'].astype(str).str.replace(',', '.'), errors='coerce')

hdn_coords = {}
# Ưu tiên lấy tọa độ từ Excel
for _, row in df_hdn.iterrows():
    name = normalize_node(row['Tên đối tượng'])
    lat, lng = row['Lat_clean'], row['Lng_clean']
    if pd.notnull(lat) and pd.notnull(lng):
        hdn_coords[name] = (float(lat), float(lng))

# Bổ sung/Ghi đè từ JSON API nếu Excel thiếu
for name, coord in json_nodes.items():
    if name not in hdn_coords:
        hdn_coords[name] = coord

# 5. Xây dựng đồ thị mạng cáp
G = nx.Graph()
for _, row in df_cable.iterrows():
    u = normalize_node(row['Điểm KN1'])
    v = normalize_node(row['Điểm KN2'])
    cable_name = str(row['Tên đoạn cáp']).strip()
    try:
        length = float(row['Chiều dài thực (m)'])
    except (ValueError, TypeError):
        length = 0.0
    if u and v:
        G.add_edge(u, v, cable=cable_name, length=length)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def interpolate_on_polyline(coords, target_offset):
    if not coords or len(coords) < 2:
        return None
    accumulated = 0.0
    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i+1]
        seg_len = haversine(p1[0], p1[1], p2[0], p2[1])
        if accumulated + seg_len >= target_offset:
            remain = target_offset - accumulated
            ratio = remain / seg_len if seg_len > 0 else 0
            return p1[0] + ratio * (p2[0] - p1[0]), p1[1] + ratio * (p2[1] - p1[1])
        accumulated += seg_len
    return coords[-1][0], coords[-1][1]

# 6. Giao diện Sidebar Streamlit
if 'search_performed' not in st.session_state:
    st.session_state.search_performed = False

map_data = None
all_nodes = sorted(list(G.nodes()))

with st.sidebar:
    st.title("📍XÁC ĐỊNH ĐIỂM ĐỨT")
    st.markdown("---")
    
    selected_td_a = st.selectbox("Nhập / Chọn TĐ Đo:", options=all_nodes, index=0 if all_nodes else None)
    
    related_nodes = []
    if selected_td_a and G.has_node(selected_td_a):
        related_nodes = sorted(list(nx.node_connected_component(G, selected_td_a)))
        related_nodes = [node for node in related_nodes if node != selected_td_a]

    selected_td_b = st.selectbox("Chọn TĐ Đến:", options=related_nodes if related_nodes else ["Không có tập điểm"], disabled=not related_nodes)
    target_dist_input = st.number_input("Khoảng cách đo được (mét):", min_value=0.0, value=100.0, step=1.0)

    if st.button("🔍 Tìm vị trí sự cố", type="primary", use_container_width=True):
        if selected_td_a and selected_td_b and selected_td_b in related_nodes:
            st.session_state.search_performed = True
            st.session_state.td_a = selected_td_a
            st.session_state.td_b = selected_td_b
            st.session_state.target_dist = target_dist_input

    if st.session_state.search_performed:
        st.markdown("---")
        td_a, td_b, target_dist = st.session_state.td_a, st.session_state.td_b, st.session_state.target_dist

        if nx.has_path(G, td_a, td_b):
            node_path = nx.shortest_path(G, td_a, td_b, weight='length')
            cable_segments = []
            accumulated_dist = 0.0
            target_segment = None

            for i in range(len(node_path) - 1):
                u, v = node_path[i], node_path[i+1]
                edge_data = G[u][v]
                seg_len = edge_data['length']
                start_d = accumulated_dist
                accumulated_dist += seg_len
                
                seg_info = {'u': u, 'v': v, 'cable': edge_data['cable'], 'length': seg_len, 'start_dist': start_d, 'end_dist': accumulated_dist}
                cable_segments.append(seg_info)

                if start_d <= target_dist <= accumulated_dist and target_segment is None:
                    target_segment = seg_info

            st.info(f"📏 **Chiều dài tuyến:** {accumulated_dist:.1f} m")

            if target_segment:
                cable_name = target_segment['cable']
                offset = target_dist - target_segment['start_dist']
                fault_lat, fault_lng = None, None

                if cable_name in json_cable_shapes:
                    fault_lat, fault_lng = interpolate_on_polyline(json_cable_shapes[cable_name], offset)

                if fault_lat is None or fault_lng is None:
                    u_coord, v_coord = hdn_coords.get(target_segment['u']), hdn_coords.get(target_segment['v'])
                    if u_coord and v_coord:
                        ratio = offset / target_segment['length'] if target_segment['length'] > 0 else 0
                        fault_lat = u_coord[0] + ratio * (v_coord[0] - u_coord[0])
                        fault_lng = u_coord[1] + ratio * (v_coord[1] - u_coord[1])

                if fault_lat and fault_lng:
                    st.success(f"⚠️ **Vị trí đứt trong đoạn cáp:**\n\n**{cable_name}**")
                    map_data = {'fault_lat': fault_lat, 'fault_lng': fault_lng, 'node_path': node_path, 'cable_segments': cable_segments, 'td_a': td_a, 'td_b': td_b, 'target_dist': target_dist}

# 7. Hiển thị Bản đồ Folium
if map_data:
    m = folium.Map(location=[map_data['fault_lat'], map_data['fault_lng']], zoom_start=17, tiles=None, zoom_control=False)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", attr="Google", name="Google Đường phố").add_to(m)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Google Vệ tinh").add_to(m)
    LocateControl(auto_start=False, flyTo=True).add_to(m)
    folium.LayerControl().add_to(m)

    # Lộ trình kết nối cáp giữa các tập điểm
    full_route_coords = []
    for seg in map_data['cable_segments']:
        c_name = seg['cable']
        if c_name in json_cable_shapes:
            full_route_coords.extend(json_cable_shapes[c_name])
        else:
            u_coord, v_coord = hdn_coords.get(seg['u']), hdn_coords.get(seg['v'])
            if u_coord: full_route_coords.append(u_coord)
            if v_coord: full_route_coords.append(v_coord)

    if full_route_coords:
        AntPath(locations=full_route_coords, color="#FF5F1F", pulse_color="#FFFFFF", weight=6, opacity=0.9, tooltip="Tuyến cáp kết nối").add_to(m)

    for node in map_data['node_path']:
        if node in hdn_coords:
            coord = hdn_coords[node]
            folium.Marker(coord, popup=f"<b>{node}</b>", tooltip=node, icon=folium.Icon(color="green" if node==map_data['td_a'] else "blue", icon="circle", prefix="fa")).add_to(m)

    folium.Marker([map_data['fault_lat'], map_data['fault_lng']], tooltip="Vị trí đứt cáp", icon=folium.Icon(color="red", icon="wrench", prefix="fa")).add_to(m)
    apply_map_custom_css(m)
    st_folium(m, width="100%", height=1000, key="fault_map")
else:
    init_lat, init_lng = 21.799, 105.211  # Tọa độ mặc định khu vực TQGP
    if hdn_coords:
        first_coord = list(hdn_coords.values())[0]
        init_lat, init_lng = first_coord[0], first_coord[1]

    default_map = folium.Map(location=[init_lat, init_lng], zoom_start=15, tiles=None, zoom_control=False)
    folium.TileLayer("https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", attr="Google").add_to(default_map)

    # Hiển thị tất cả các tuyến cáp dựa vào bảng kết nối giữa các tập điểm
    for u, v, data in G.edges(data=True):
        if u in hdn_coords and v in hdn_coords:
            folium.PolyLine([hdn_coords[u], hdn_coords[v]], color="#2563EB", weight=3, opacity=0.8, tooltip=f"Đoạn cáp: {data.get('cable', '')}").add_to(default_map)

    apply_map_custom_css(default_map)
    st_folium(default_map, width="100%", height=1000, key="default_map")
