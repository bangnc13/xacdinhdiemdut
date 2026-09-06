import os
import re
import json
import math
import glob
import requests
import networkx as nx
import pandas as pd
import streamlit as st
import folium
from folium import DivIcon
from folium.plugins import LocateControl, AntPath
from streamlit_folium import st_folium
from PIL import Image

# 1. Cấu hình trang
st.set_page_config(
    page_title="Make by BangNC13",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject CSS Custom Streamlit
st.markdown("""
    <style>
    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 999999 !important; pointer-events: none; }
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
    }

    .block-container { padding: 0rem !important; max-width: 100% !important; }

    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.15) !important;
        backdrop-filter: blur(18px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(18px) saturate(180%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.3) !important;
        z-index: 999998 !important;
    }

    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #1D4ED8 !important;
        font-weight: 700 !important;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Các hàm bổ trợ toán học & địa lý
def normalize_node(node_str):
    if pd.isna(node_str): return ""
    s = str(node_str).strip()
    s = re.sub(r'/\d+$', '', s)
    match = re.match(r'([A-Za-z0-9]+)\.(\d+)/([A-Za-z0-9]+)', s)
    if match:
        prefix, num, suffix = match.groups()
        return f"{prefix}.{int(num):04d}/{suffix}"
    return s

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def calculate_polyline_length(coords):
    if not coords or len(coords) < 2: return 0.0
    return sum(haversine(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1]) for i in range(len(coords) - 1))

@st.cache_data(ttl=3600)
def get_osrm_route(lat1, lon1, lat2, lon2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        res = requests.get(url, timeout=2)
        if res.status_code == 200:
            data = res.json()
            if data.get("routes"):
                coords = data["routes"][0]["geometry"]["coordinates"]
                return [[p[1], p[0]] for p in coords]
    except Exception:
        pass
    return [[lat1, lon1], [lat2, lon2]]

def process_segment_geometry(raw_coords, u_coord, v_coord, target_length):
    if not raw_coords:
        if u_coord and v_coord:
            raw_coords = get_osrm_route(u_coord[0], u_coord[1], v_coord[0], v_coord[1])
        else:
            return []

    if u_coord:
        d_start = haversine(u_coord[0], u_coord[1], raw_coords[0][0], raw_coords[0][1])
        d_end = haversine(u_coord[0], u_coord[1], raw_coords[-1][0], raw_coords[-1][1])
        if d_end < d_start:
            raw_coords = list(reversed(raw_coords))

    first_p, last_p = raw_coords[0], raw_coords[-1]
    if haversine(first_p[0], first_p[1], last_p[0], last_p[1]) < 20.0 and len(raw_coords) > 4:
        mid_idx = len(raw_coords) // 2
        path_top = raw_coords[:mid_idx+1]
        path_bottom = raw_coords[mid_idx:] + [raw_coords[0]]
        
        len_top = calculate_polyline_length(path_top)
        len_bottom = calculate_polyline_length(path_bottom)
        
        raw_coords = path_top if abs(len_top - target_length) < abs(len_bottom - target_length) else path_bottom

    return raw_coords

def interpolate_on_polyline_scaled(coords, target_offset, decl_length):
    if not coords or len(coords) < 2: return None
    
    geo_length = calculate_polyline_length(coords)
    scale_factor = geo_length / decl_length if (decl_length > 0 and geo_length > 0) else 1.0
    adjusted_target = target_offset * scale_factor

    accumulated = 0.0
    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i+1]
        seg_len = haversine(p1[0], p1[1], p2[0], p2[1])
        if accumulated + seg_len >= adjusted_target:
            remain = adjusted_target - accumulated
            ratio = remain / seg_len if seg_len > 0 else 0
            return p1[0] + ratio * (p2[0] - p1[0]), p1[1] + ratio * (p2[1] - p1[1])
        accumulated += seg_len
    return coords[-1][0], coords[-1][1]

def apply_map_custom_css(folium_map):
    font_awesome_link = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
    folium_map.get_root().html.add_child(folium.Element(font_awesome_link))
    custom_css = """
    <style>
    .leaflet-control-zoom { display: none !important; }
    .leaflet-control-locate { margin-top: 70px !important; margin-left: 10px !important; border: none !important; }
    .leaflet-control-locate a {
        background-color: #2563EB !important; color: #FFFFFF !important;
        border-radius: 8px !important; width: 36px !important; height: 36px !important;
        display: flex !important; align-items: center !important; justify-content: center !important;
    }
    .leaflet-control-layers { margin-top: 70px !important; margin-right: 10px !important; border-radius: 8px !important; }
    </style>
    """
    folium_map.get_root().html.add_child(folium.Element(custom_css))

# 4. TỐI ƯU HÓA LOAD DỮ LIỆU & TÍNH TOÁN DỮ LIỆU ĐỘNG (CACHE TOÀN BỘ)
@st.cache_data(ttl=3600, show_spinner="Đang xử lý dữ liệu hệ thống...")
def get_processed_data():
    file_path = "Data.xlsx"
    df_uplink = pd.read_excel(file_path, sheet_name="uplink")
    df_cable = pd.read_excel(file_path, sheet_name="Đoạn cáp")
    df_hdn = pd.read_excel(file_path, sheet_name="HĐN")

    # 4.1 Tọa độ HĐN
    df_hdn['Lat_clean'] = pd.to_numeric(df_hdn['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
    df_hdn['Lng_clean'] = pd.to_numeric(df_hdn['Lng'].astype(str).str.replace(',', '.'), errors='coerce')
    
    hdn_coords = {}
    for _, row in df_hdn.iterrows():
        name = normalize_node(row['Tên đối tượng'])
        lat, lng = row['Lat_clean'], row['Lng_clean']
        if pd.notnull(lat) and pd.notnull(lng):
            hdn_coords[name] = (float(lat), float(lng))

    # 4.2 Bản đồ Phân cấp (Level Map)
    node_level_map = {}
    has_col_d = df_uplink.shape[1] >= 4
    for idx, row in df_uplink.iterrows():
        node_name = normalize_node(row['Tên đối tượng'] if 'Tên đối tượng' in row else row['TĐ'])
        if not node_name: continue
        
        level = None
        if has_col_d and pd.notnull(row.iloc[3]):
            val_d = str(row.iloc[3]).strip().lower()
            if "1" in val_d: level = 1
            elif "2" in val_d: level = 2
        
        if level is None:
            level = 2 if (node_name.endswith('/HO') or node_name.endswith('/MO')) else 1
        
        node_level_map[node_name] = level

    # 4.3 Đồ thị cáp NetworkX
    G = nx.Graph()
    for _, row in df_cable.iterrows():
        u = normalize_node(row['Điểm KN1'])
        v = normalize_node(row['Điểm KN2'])
        cable_name = str(row['Tên đoạn cáp']).strip()
        
        try: length = float(row['Chiều dài thực (m)'])
        except: length = 0.0
        
        cap_val = row.get('Dung lượng') if 'Dung lượng' in df_cable.columns else row.iloc[5]
        if pd.isna(cap_val) or str(cap_val).strip() in ["", "nan", "None"]:
            capacity_str = "Chưa xác định"
        else:
            try: capacity_str = f"{int(float(cap_val))} FO"
            except: capacity_str = f"{str(cap_val).strip()} FO" if "FO" not in str(cap_val).upper() else str(cap_val).strip()

        if u and v: 
            G.add_edge(u, v, cable=cable_name, length=length, capacity=capacity_str)

    # 4.4 Load JSON shapes
    cable_shapes = {}
    for json_file_path in glob.glob("*.json"):
        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                for feature in data.get("features", []):
                    props = feature.get("properties", {})
                    cable_name = props.get("name") or props.get("TEN_DOAN_CAP") or props.get("code") or props.get("id")
                    geom = feature.get("geometry", {})
                    if geom.get("type") == "LineString":
                        coords = [[p[1], p[0]] for p in geom.get("coordinates", [])]
                        if cable_name: cable_shapes[str(cable_name).strip()] = coords
                    elif geom.get("type") == "MultiLineString":
                        coords = []
                        for line in geom.get("coordinates", []):
                            coords.extend([[p[1], p[0]] for p in line])
                        if cable_name: cable_shapes[str(cable_name).strip()] = coords
        except Exception:
            pass

    return G, hdn_coords, node_level_map, cable_shapes

# Tải nhanh toàn bộ cấu trúc dữ liệu đã cache
try:
    G, hdn_coords, node_level_map, json_cable_shapes = get_processed_data()
    all_nodes = sorted(list(G.nodes()))
except Exception as e:
    st.error(f"Lỗi khởi tạo dữ liệu: {e}")
    st.stop()

def get_node_level(node_name):
    if node_name in node_level_map: return node_level_map[node_name]
    return 2 if (node_name.endswith('/HO') or node_name.endswith('/MO')) else 1

if 'search_performed' not in st.session_state:
    st.session_state.search_performed = False

map_data = None

# 5. GIAO DIỆN BÊN TRÁI & TỐI ƯU THUẬT TOÁN LỌC TĐ
with st.sidebar:
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    logo_path = os.path.join(current_dir, "FPT_Telecom_logo.png")
    if os.path.exists(logo_path):
        st.image(Image.open(logo_path), use_container_width=True)
    else:
        st.image("https://upload.wikimedia.org/wikipedia/commons/1/11/FPT_Telecom_logo.svg", width=220)

    st.title("📍XÁC ĐỊNH ĐIỂM ĐỨT")
    st.markdown("---")
    
    selected_td_a = st.selectbox("Nhập / Chọn TĐ Đo:", options=all_nodes, index=0 if all_nodes else None)
    
    # Lọc nhanh danh sách TĐ phù hợp
    related_nodes = []
    if selected_td_a and G.has_node(selected_td_a):
        connected_nodes = nx.node_connected_component(G, selected_td_a)
        level_a = get_node_level(selected_td_a)
        
        if level_a == 2:
            related_nodes = sorted([
                node for node in connected_nodes
                if node != selected_td_a 
                and not (node.endswith('/TO') or node.endswith('/FO'))
                and get_node_level(node) in [1, 2]
            ])
        else:
            related_nodes = sorted([
                node for node in connected_nodes
                if node != selected_td_a 
                and not (node.endswith('/TO') or node.endswith('/FO'))
            ])

    if related_nodes:
        selected_td_b = st.selectbox(
            f"Chọn TĐ Đến ({len(related_nodes)} TĐ phù hợp):", 
            options=related_nodes, 
            index=0
        )
    else:
        selected_td_b = st.selectbox("Chọn TĐ Đến:", options=["Không có tập điểm liên quan hợp lệ"], disabled=True)

    target_dist_input = st.number_input("Khoảng cách đo được (mét):", min_value=0.0, value=100.0, step=1.0)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🔍 Tìm vị trí sự cố", type="primary", use_container_width=True):
        if selected_td_a and selected_td_b and selected_td_b in related_nodes:
            st.session_state.search_performed = True
            st.session_state.td_a = selected_td_a
            st.session_state.td_b = selected_td_b
            st.session_state.target_dist = target_dist_input

    if st.session_state.search_performed:
        st.markdown("---")
        st.subheader("📊 Kết Quả Phân Tích")
        
        td_a, td_b, target_dist = st.session_state.td_a, st.session_state.td_b, st.session_state.target_dist

        if not nx.has_path(G, td_a, td_b):
            st.error(f"Không tìm thấy tuyến cáp nối giữa {td_a} và {td_b}!")
        else:
            node_path = nx.shortest_path(G, td_a, td_b, weight='length')
            cable_segments, accumulated_dist, target_segment = [], 0.0, None

            for i in range(len(node_path) - 1):
                u, v = node_path[i], node_path[i+1]
                edge_data = G[u][v]
                seg_len = edge_data['length']
                start_d = accumulated_dist
                accumulated_dist += seg_len
                
                seg_info = {
                    'u': u, 'v': v, 
                    'cable': edge_data['cable'], 
                    'length': seg_len, 
                    'capacity': edge_data.get('capacity', 'Chưa xác định'),
                    'start_dist': start_d, 
                    'end_dist': accumulated_dist
                }
                cable_segments.append(seg_info)
                if start_d <= target_dist <= accumulated_dist and target_segment is None:
                    target_segment = seg_info

            st.info(f"📏 **Chiều dài tổng tuyến:** {accumulated_dist:.1f} m")

            if target_dist > accumulated_dist:
                st.error(f"Khoảng cách nhập vào ({target_dist}m) vượt quá chiều dài tuyến ({accumulated_dist:.1f}m)!")
            elif target_segment:
                cable_name = target_segment['cable']
                offset_from_u = target_dist - target_segment['start_dist']  # Khoảng cách từ đầu u
                offset_from_v = target_segment['length'] - offset_from_u    # Khoảng cách đến cuối v

                u_coord = hdn_coords.get(target_segment['u'])
                v_coord = hdn_coords.get(target_segment['v'])

                raw_coords = json_cable_shapes.get(cable_name, [])
                processed_coords = process_segment_geometry(raw_coords, u_coord, v_coord, target_segment['length'])
                fault_lat, fault_lng = interpolate_on_polyline_scaled(processed_coords, offset_from_u, target_segment['length'])

                if fault_lat and fault_lng:
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #D1FAE5; 
                            border: 1px solid #10B981; 
                            border-radius: 8px; 
                            padding: 16px; 
                            color: #1D4ED8; 
                            font-weight: 600;
                            margin-bottom: 16px;
                        ">
                        ⚠️ <b>Vị trí đứt nằm trong đoạn cáp:</b><br><br>
                        <b>{cable_name}</b><br><br>
                        📍 <b>Lộ trình đoạn:</b> {target_segment['u']} ➔ {target_segment['v']}<br><br>
                        📏 <b>Chiều dài đoạn cáp lỗi:</b> {target_segment['length']:.1f} m<br><br>
                        🔌 <b>Dung lượng đoạn cáp:</b> {target_segment['capacity']}<br><br>
                        <hr style="border-top: 1px solid #1D4ED8;">
                        🎯 <b>Chi tiết vị trí điểm đứt:</b><br>
                        - Cách <b>{target_segment['u']}</b> (Đầu đoạn): <b>{offset_from_u:.1f} m</b><br>
                        - Cách <b>{target_segment['v']}</b> (Cuối đoạn): <b>{offset_from_v:.1f} m</b>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={fault_lat},{fault_lng}"
                    st.link_button("📍 Mở chỉ đường Google Maps", gmaps_url, type="primary", use_container_width=True)

                    map_data = {
                        'fault_lat': fault_lat, 'fault_lng': fault_lng,
                        'node_path': node_path, 'cable_segments': cable_segments,
                        'td_a': td_a, 'td_b': td_b, 'target_dist': target_dist
                    }

# 6. BẢN ĐỒ INTERACTIVE
if map_data:
    m = folium.Map(location=[map_data['fault_lat'], map_data['fault_lng']], zoom_start=17, tiles=None, zoom_control=False)
    folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", attr="Google", name="Đường phố", overlay=False).add_to(m)
    folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Vệ tinh", overlay=False).add_to(m)
    LocateControl(auto_start=False, flyTo=True, icon="fa fa-location-arrow").add_to(m)
    folium.LayerControl().add_to(m)

    full_route_coords = []
    for seg in map_data['cable_segments']:
        c_name = seg['cable']
        u_coord, v_coord = hdn_coords.get(seg['u']), hdn_coords.get(seg['v'])
        raw_coords = json_cable_shapes.get(c_name, [])
        seg_coords = process_segment_geometry(raw_coords, u_coord, v_coord, seg['length'])
        full_route_coords.extend(seg_coords)

    if full_route_coords:
        AntPath(locations=full_route_coords, color="#FF5F1F", pulse_color="#FFFFFF", weight=6, opacity=0.9, delay=1000, tooltip="Tuyến cáp theo thực địa").add_to(m)

    for node in map_data['node_path']:
        if node in hdn_coords:
            coord = hdn_coords[node]
            icon_color = "green" if node == map_data['td_a'] else ("black" if node == map_data['td_b'] else "blue")
            icon_name = "play" if node == map_data['td_a'] else ("flag-checkered" if node == map_data['td_b'] else "circle")

            folium.Marker(coord, popup=f"<b>{node}</b>", tooltip=node, icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa")).add_to(m)
            label_html = f'<div style="font-size:12px; font-weight:800; color:#DC2626; background:rgba(255,255,255,0.95); border:1.5px solid #EF4444; padding:2px 6px; border-radius:4px; white-space:nowrap;">{node}</div>'
            folium.Marker(coord, icon=DivIcon(icon_size=(150, 36), icon_anchor=(-15, 12), html=label_html)).add_to(m)

    folium.Marker([map_data['fault_lat'], map_data['fault_lng']], popup=f"Điểm đứt: {map_data['target_dist']}m từ {map_data['td_a']}", tooltip="Vị trí đứt cáp", icon=folium.Icon(color="red", icon="wrench", prefix="fa")).add_to(m)
    apply_map_custom_css(m)
    st_folium(m, width="100%", height=1000, key="fault_map")
else:
    init_lat, init_lng = 21.0285, 105.8542
    default_map = folium.Map(location=[init_lat, init_lng], zoom_start=13, tiles=None, zoom_control=False)
    folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", attr="Google", name="Google Maps", overlay=False).add_to(default_map)
    apply_map_custom_css(default_map)
    st_folium(default_map, width="100%", height=1000, key="default_map")
