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

    button[data-testid="stHeaderIconButton"]:hover,
    [data-testid="stSidebarCollapseButton"] button:hover {
        background-color: #FED7AA !important;
        border-color: #FF7F3E !important;
        box-shadow: 0 0 15px rgba(255, 127, 62, 0.8), 0 4px 15px rgba(0, 0, 0, 0.3) !important;
        transform: scale(1.08);
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
        -webkit-backdrop-filter: blur(18px) saturate(180%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.3) !important;
        z-index: 999998 !important;
        box-shadow: 4px 0 20px rgba(0, 0, 0, 0.05) !important;
    }

    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: #1D4ED8 !important;
        font-weight: 700 !important;
        text-shadow: none !important;
    }

    [data-testid="stSidebar"] h1 {
        color: #1E40AF !important;
        text-shadow: none !important;
    }

    [data-testid="stSidebar"] input, 
    [data-testid="stSidebar"] div[data-baseweb="select"] {
        background-color: rgba(255, 255, 255, 0.5) !important;
        color: #1D4ED8 !important;
        border: 1px solid rgba(37, 99, 235, 0.4) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        text-shadow: none !important;
    }

    div[data-baseweb="popover"] {
        background-color: rgba(255, 255, 255, 0.95) !important;
        color: #1D4ED8 !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: rgba(37, 99, 235, 0.3) !important;
    }

    [data-testid="stSidebar"] .stButton > button, 
    [data-testid="stSidebar"] .stLinkButton > a {
        background-color: #FFEDD5 !important;
        color: #C2410C !important;
        border: 1.5px solid #FDBA74 !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        box-shadow: 0 2px 8px rgba(234, 88, 12, 0.15) !important;
        transition: all 0.2s ease-in-out !important;
        text-shadow: none !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover, 
    [data-testid="stSidebar"] .stLinkButton > a:hover {
        background-color: #FED7AA !important;
        color: #9A3412 !important;
        border-color: #FB923C !important;
        box-shadow: 0 4px 12px rgba(234, 88, 12, 0.3) !important;
    }

    iframe {
        border: none !important;
    }
    </style>
""", unsafe_allow_html=True)

def apply_map_custom_css(folium_map, fault_lat=None, fault_lng=None):
    font_awesome_link = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
    folium_map.get_root().html.add_child(folium.Element(font_awesome_link))

    nav_button_html = ""
    if fault_lat and fault_lng:
        # Sử dụng đường dẫn URL dạng Google Maps Navigation tiêu chuẩn
        # Khi nhấn vào trên thiết bị di động, hệ thống sẽ tự hỏi mở ứng dụng Google Maps
        gmaps_nav_url = f"https://www.google.com/maps/dir/?api=1&destination={fault_lat},{fault_lng}&travelmode=driving"
        
        nav_button_html = f"""
        <div style="position: absolute; top: 15px; left: 60px; z-index: 1000;">
            <a href="{gmaps_nav_url}" target="_blank" style="
                background-color: #059669;
                color: white;
                border: none;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                display: flex;
                align-items: center;
                gap: 8px;
                text-decoration: none;
                font-family: sans-serif;
            " onmouseover="this.style.backgroundColor='#047857'" onmouseout="this.style.backgroundColor='#059669'">
                <i class="fa-solid fa-diamond-turn-right"></i> Chỉ đường Google Maps
            </a>
        </div>
        """

    custom_css = f"""
    <style>
    .leaflet-control-zoom {{ display: none !important; }}
    .leaflet-control-locate {{
        margin-top: 70px !important;
        margin-left: 10px !important;
        border: none !important;
    }}
    .leaflet-control-locate a {{
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        width: 36px !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    .leaflet-control-locate a span.fa,
    .leaflet-control-locate a span.fas {{
        font-size: 16px !important;
        color: #FFFFFF !important;
    }}
    .leaflet-control-layers {{
        margin-top: 70px !important;
        margin-right: 10px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
    }}
    </style>
    {nav_button_html}
    """
    folium_map.get_root().html.add_child(folium.Element(custom_css))

# 3. Tải dữ liệu Excel & JSON
@st.cache_data
def load_data():
    file_path = "Data.xlsx"
    df_uplink = pd.read_excel(file_path, sheet_name="uplink")
    df_cable = pd.read_excel(file_path, sheet_name="Đoạn cáp")
    df_hdn = pd.read_excel(file_path, sheet_name="HĐN")
    return df_uplink, df_cable, df_hdn

@st.cache_data
def load_json_cable_shapes(json_file_path="TQGP001.json"):
    cable_shapes = {}
    if not os.path.exists(json_file_path):
        return cable_shapes
        
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
                    if cable_name:
                        cable_shapes[str(cable_name).strip()] = coords
                elif geom.get("type") == "MultiLineString":
                    coords = []
                    for line in geom.get("coordinates", []):
                        coords.extend([[p[1], p[0]] for p in line])
                    if cable_name:
                        cable_shapes[str(cable_name).strip()] = coords

        elif isinstance(data, list):
            for item in data:
                cable_name = item.get("cable_name") or item.get("name") or item.get("code")
                coords = item.get("coordinates") or item.get("points") or item.get("path")
                if cable_name and coords:
                    formatted_coords = []
                    for pt in coords:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            if pt[0] > pt[1]:
                                formatted_coords.append([pt[1], pt[0]])
                            else:
                                formatted_coords.append([pt[0], pt[1]])
                    if formatted_coords:
                        cable_shapes[str(cable_name).strip()] = formatted_coords
    except Exception as e:
        st.error(f"Lỗi khi đọc file TQGP001.json: {e}")

    return cable_shapes

try:
    df_uplink, df_cable, df_hdn = load_data()
    json_cable_shapes = load_json_cable_shapes("TQGP001.json")
except Exception as e:
    st.error(f"Lỗi khi tải dữ liệu: {e}")
    st.stop()

# Chuẩn hóa tên tập điểm
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

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
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
            lat = p1[0] + ratio * (p2[0] - p1[0])
            lng = p1[1] + ratio * (p2[1] - p1[1])
            return lat, lng
        accumulated += seg_len
    return coords[-1][0], coords[-1][1]

# 4. Xây dựng đồ thị mạng cáp
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

# 5. Trích xuất tọa độ HĐN
df_hdn['Lat_clean'] = pd.to_numeric(df_hdn['Lat'].astype(str).str.replace(',', '.'), errors='coerce')
df_hdn['Lng_clean'] = pd.to_numeric(df_hdn['Lng'].astype(str).str.replace(',', '.'), errors='coerce')

hdn_coords = {}
for _, row in df_hdn.iterrows():
    name = normalize_node(row['Tên đối tượng'])
    lat = row['Lat_clean']
    lng = row['Lng_clean']
    if pd.notnull(lat) and pd.notnull(lng):
        hdn_coords[name] = (float(lat), float(lng))

if 'search_performed' not in st.session_state:
    st.session_state.search_performed = False

map_data = None
all_nodes = sorted(list(G.nodes()))

# 6. MENU DẠNG DỌC BÊN TRÁI (SIDEBAR)
with st.sidebar:
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    logo_path = os.path.join(current_dir, "FPT_Telecom_logo.png")
    
    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path)
            st.image(logo_img, use_container_width=True)
        except Exception:
            st.image("https://upload.wikimedia.org/wikipedia/commons/1/11/FPT_Telecom_logo.svg", width=220)
    else:
        st.image("https://upload.wikimedia.org/wikipedia/commons/1/11/FPT_Telecom_logo.svg", width=220)

    st.title("📍XÁC ĐỊNH ĐIỂM ĐỨT")
    st.markdown("---")
    
    selected_td_a = st.selectbox(
        "Nhập / Chọn TĐ Đo:",
        options=all_nodes,
        index=0 if all_nodes else None
    )
    
    related_nodes = []
    if selected_td_a and G.has_node(selected_td_a):
        related_nodes = sorted(list(nx.node_connected_component(G, selected_td_a)))
        related_nodes = [node for node in related_nodes if node != selected_td_a]

    if related_nodes:
        selected_td_b = st.selectbox(
            "Chọn TĐ Đến (Đã lọc theo TĐ Đo):",
            options=related_nodes,
            index=0
        )
    else:
        selected_td_b = st.selectbox(
            "Chọn TĐ Đến:",
            options=["Không có tập điểm liên quan"],
            disabled=True
        )

    target_dist_input = st.number_input("Khoảng cách đo được (mét):", min_value=0.0, value=100.0, step=1.0)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🔍 Tìm vị trí sự cố", type="primary", use_container_width=True):
        if selected_td_a and selected_td_b and selected_td_b in related_nodes:
            st.session_state.search_performed = True
            st.session_state.td_a = selected_td_a
            st.session_state.td_b = selected_td_b
            st.session_state.target_dist = target_dist_input
        else:
            st.error("Vui lòng chọn TĐ Đo và TĐ Đến hợp lệ!")

    if st.session_state.search_performed:
        st.markdown("---")
        st.subheader("📊 Kết Quả Phân Tích")
        
        td_a = st.session_state.td_a
        td_b = st.session_state.td_b
        target_dist = st.session_state.target_dist

        if not nx.has_path(G, td_a, td_b):
            st.error(f"Không tìm thấy tuyến cáp nối giữa {td_a} và {td_b}!")
        else:
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
                
                seg_info = {
                    'u': u,
                    'v': v,
                    'cable': edge_data['cable'],
                    'length': seg_len,
                    'start_dist': start_d,
                    'end_dist': accumulated_dist
                }
                cable_segments.append(seg_info)

                if start_d <= target_dist <= accumulated_dist and target_segment is None:
                    target_segment = seg_info

            st.info(f"📏 **Chiều dài tuyến:** {accumulated_dist:.1f} m")

            if target_dist > accumulated_dist:
                st.error(f"Khoảng cách nhập vào ({target_dist}m) vượt quá tổng chiều dài tuyến ({accumulated_dist:.1f}m)!")
            elif target_segment:
                cable_name = target_segment['cable']
                offset = target_dist - target_segment['start_dist']
                fault_lat, fault_lng = None, None

                if cable_name in json_cable_shapes:
                    raw_coords = json_cable_shapes[cable_name]
                    fault_lat, fault_lng = interpolate_on_polyline(raw_coords, offset)

                if fault_lat is None or fault_lng is None:
                    u_coord = hdn_coords.get(target_segment['u'])
                    v_coord = hdn_coords.get(target_segment['v'])
                    if u_coord and v_coord:
                        ratio = offset / target_segment['length'] if target_segment['length'] > 0 else 0
                        fault_lat = u_coord[0] + ratio * (v_coord[0] - u_coord[0])
                        fault_lng = u_coord[1] + ratio * (v_coord[1] - u_coord[1])

                if fault_lat and fault_lng:
                    st.success(f"⚠️ **Vị trí đứt nằm trong đoạn cáp:**\n\n**{cable_name}**\n\n({target_segment['u']} ➔ {target_segment['v']})")
                    
                    gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={fault_lat},{fault_lng}&travelmode=driving"
                    st.link_button("📍 Mở chỉ đường Google Maps", gmaps_url, type="primary", use_container_width=True)

                    map_data = {
                        'fault_lat': fault_lat,
                        'fault_lng': fault_lng,
                        'node_path': node_path,
                        'cable_segments': cable_segments,
                        'td_a': td_a,
                        'td_b': td_b,
                        'target_dist': target_dist
                    }
                else:
                    st.warning("Thiếu dữ liệu tọa độ Lat/Lng cho đoạn cáp chứa vị trí đứt.")

# 7. BẢN ĐỒ FULL TRÀN VIỀN BÊN PHẢI
if map_data:
    m = folium.Map(
        location=[map_data['fault_lat'], map_data['fault_lng']], 
        zoom_start=17,
        tiles=None,
        zoom_control=False
    )

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Maps Đường phố",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Maps Vệ tinh",
        overlay=False,
        control=True
    ).add_to(m)

    LocateControl(
        auto_start=False, 
        flyTo=True, 
        icon="fa fa-location-arrow", 
        iconLoading="fa fa-spinner fa-spin"
    ).add_to(m)
    
    folium.LayerControl().add_to(m)

    # Hiển thị lộ trình bằng AntPath
    full_route_coords = []
    for seg in map_data['cable_segments']:
        c_name = seg['cable']
        if c_name in json_cable_shapes:
            full_route_coords.extend(json_cable_shapes[c_name])
        else:
            u_coord = hdn_coords.get(seg['u'])
            v_coord = hdn_coords.get(seg['v'])
            if u_coord:
                full_route_coords.append(u_coord)
            if v_coord:
                full_route_coords.append(v_coord)

    if full_route_coords:
        AntPath(
            locations=full_route_coords,
            color="#FF5F1F",
            pulse_color="#FFFFFF",
            weight=6,
            opacity=0.9,
            delay=1000,
            tooltip="Lộ trình cáp mạng"
        ).add_to(m)

    # Hiển thị Marker và Nhãn tên TĐ
    for node in map_data['node_path']:
        if node in hdn_coords:
            coord = hdn_coords[node]
            
            if node == map_data['td_a']:
                icon_color, icon_name = "green", "play"
            elif node == map_data['td_b']:
                icon_color, icon_name = "black", "flag-checkered"
            else:
                icon_color, icon_name = "blue", "circle"

            folium.Marker(
                coord,
                popup=f"<b>{node}</b>",
                tooltip=node,
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa")
            ).add_to(m)

            label_html = f'''
                <div style="
                    font-size: 12px;
                    font-weight: 800;
                    color: #DC2626;
                    background-color: rgba(255, 255, 255, 0.95);
                    border: 1.5px solid #EF4444;
                    padding: 2px 6px;
                    border-radius: 4px;
                    white-space: nowrap;
                    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
                    display: inline-block;
                ">{node}</div>
            '''

            folium.Marker(
                coord,
                icon=DivIcon(
                    icon_size=(150, 36),
                    icon_anchor=(-15, 12),
                    html=label_html
                )
            ).add_to(m)

    # Marker Vị trí đứt cáp + Popup hỗ trợ mở chỉ đường
    popup_html = f"""
    <div style="font-family: sans-serif; min-width: 160px; text-align: center;">
        <h4 style="margin: 0 0 8px 0; color: #DC2626;">Vị trí đứt cáp</h4>
        <p style="margin: 0 0 8px 0; font-size: 12px;">{map_data['target_dist']}m từ {map_data['td_a']}</p>
        <a href="https://www.google.com/maps/dir/?api=1&destination={map_data['fault_lat']},{map_data['fault_lng']}&travelmode=driving" 
           target="_blank" 
           style="background-color: #2563EB; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold; display: inline-block;">
           <i class="fa-solid fa-location-arrow"></i> Chỉ đường ngay
        </a>
    </div>
    """

    folium.Marker(
        [map_data['fault_lat'], map_data['fault_lng']],
        popup=folium.Popup(popup_html, max_width=250),
        tooltip="Click để mở chỉ đường vị trí sự cố",
        icon=folium.Icon(color="red", icon="wrench", prefix="fa")
    ).add_to(m)

    apply_map_custom_css(m, fault_lat=map_data['fault_lat'], fault_lng=map_data['fault_lng'])
    
    # Bổ sung các tham số Sandbox để cho phép bật tab mới từ Iframe
    st_folium(
        m, 
        width="100%", 
        height=1000, 
        key="fault_map"
    )
else:
    init_lat, init_lng = 21.0285, 105.8542
    if json_cable_shapes:
        first_cable = list(json_cable_shapes.values())[0]
        if first_cable:
            init_lat, init_lng = first_cable[0][0], first_cable[0][1]

    default_map = folium.Map(
        location=[init_lat, init_lng],
        zoom_start=14 if json_cable_shapes else 12,
        tiles=None,
        zoom_control=False
    )
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google",
        name="Google Maps Đường phố",
        overlay=False,
        control=False
    ).add_to(default_map)

    LocateControl(
        auto_start=False, 
        flyTo=True, 
        icon="fa fa-location-arrow", 
        iconLoading="fa fa-spinner fa-spin"
    ).add_to(default_map)

    for c_name, coords in json_cable_shapes.items():
        folium.PolyLine(
            coords,
            color="#2563EB",
            weight=4,
            opacity=0.7,
            tooltip=f"Tuyến cáp JSON: {c_name}"
        ).add_to(default_map)

    apply_map_custom_css(default_map)
    st_folium(default_map, width="100%", height=1000, key="default_map")
