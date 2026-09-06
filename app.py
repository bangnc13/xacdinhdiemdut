import re
import networkx as nx
import pandas as pd
import streamlit as st
import folium
from folium.plugins import LocateControl
from streamlit_folium import st_folium

# 1. Cấu hình trang Full layout
st.set_page_config(
    page_title="Xác định điểm đứt cáp & Dẫn đường",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject Custom CSS: Tạo hiệu ứng Sidebar Blur & Tràn màn hình Map
st.markdown("""
    <style>
    /* Ẩn bớt padding dư thừa của Streamlit */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }

    /* CSS Sidebar dạng kính mờ (Glassmorphism / Blur Effect) */
    [data-testid="stSidebar"] {
        background: rgba(18, 24, 38, 0.75) !important;
        backdrop-filter: blur(12px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(12px) saturate(180%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
    }

    /* Màu chữ và label trong Sidebar */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown {
        color: #f1f5f9 !important;
    }

    /* Đổi màu input trong Sidebar cho nổi bật */
    [data-testid="stSidebar"] input {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 8px !important;
    }

    /* Style cho Nút Bấm chính */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    
    /* Responsive cho màn hình Map full viền */
    iframe {
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# 3. Hàm tải dữ liệu Excel
@st.cache_data
def load_data():
    file_path = "Data.xlsx"
    df_uplink = pd.read_excel(file_path, sheet_name="uplink")
    df_cable = pd.read_excel(file_path, sheet_name="Đoạn cáp")
    df_hdn = pd.read_excel(file_path, sheet_name="HĐN")
    return df_uplink, df_cable, df_hdn

try:
    df_uplink, df_cable, df_hdn = load_data()
except Exception as e:
    st.error(f"Lỗi khi đọc file Data.xlsx: {e}")
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

# 6. MENU DẠNG DỌC BÊN TRÁI (SIDEBAR)
with st.sidebar:
    st.title("📍 Cấu Hình Sự Cố")
    st.markdown("---")
    
    td_a_input = st.text_input("Nhập TĐ A:", value="TQGP001.0011/HO")
    td_b_input = st.text_input("Nhập TĐ B:", value="TQGP001.0013/HO")
    target_dist = st.number_input("Khoảng cách từ TĐ A (mét):", min_value=0.0, value=100.0, step=1.0)
    
    st.markdown("<br>", unsafe_allow_html=True)
    search_btn = st.button("🔍 Tìm vị trí sự cố", type="primary", use_container_width=True)

# Khởi tạo trạng thái Session State
if 'search_performed' not in st.session_state:
    st.session_state.search_performed = False

if search_btn:
    st.session_state.search_performed = True
    st.session_state.td_a = normalize_node(td_a_input)
    st.session_state.td_b = normalize_node(td_b_input)
    st.session_state.target_dist = target_dist

# 7. HIỂN THỊ KẾT QUẢ & BẢN ĐỒ FULL MÀN HÌNH BÊN PHẢI
if st.session_state.search_performed:
    td_a = st.session_state.td_a
    td_b = st.session_state.td_b
    target_dist = st.session_state.target_dist

    if not td_a or not td_b:
        st.warning("Vui lòng nhập đầy đủ thông tin TĐ A và TĐ B ở menu bên trái!")
    elif not G.has_node(td_a) or not G.has_node(td_b):
        st.error("Một trong hai tập điểm nhập vào không tồn tại trong dữ liệu!")
    elif not nx.has_path(G, td_a, td_b):
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

        # Hiển thị thanh thông tin ngang trên đầu bản đồ
        info_col1, info_col2 = st.columns([1, 1])
        with info_col1:
            st.info(f"📏 Tổng chiều dài tuyến ({td_a} ➔ {td_b}): **{accumulated_dist:.1f} m**")
        
        if target_dist > accumulated_dist:
            st.error(f"Khoảng cách nhập vào ({target_dist}m) vượt quá tổng chiều dài tuyến cáp ({accumulated_dist:.1f}m)!")
        elif target_segment:
            u_coord = hdn_coords.get(target_segment['u'])
            v_coord = hdn_coords.get(target_segment['v'])

            if u_coord and v_coord:
                offset = target_dist - target_segment['start_dist']
                ratio = offset / target_segment['length'] if target_segment['length'] > 0 else 0
                
                fault_lat = u_coord[0] + ratio * (v_coord[0] - u_coord[0])
                fault_lng = u_coord[1] + ratio * (v_coord[1] - u_coord[1])

                with info_col2:
                    st.success(f"⚠️ Đoạn đứt: **{target_segment['cable']}** ({target_segment['u']} ➔ {target_segment['v']})")

                # Nút điều hướng Google Maps Dẫn đường
                gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={fault_lat},{fault_lng}"
                st.link_button("🚗 Mở Google Maps Chỉ Đường", gmaps_url, type="primary", use_container_width=True)

                # KHỞI TẠO BẢN ĐỒ
                m = folium.Map(
                    location=[fault_lat, fault_lng], 
                    zoom_start=17,
                    tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                    attr="OpenStreetMap"
                )

                # Lớp Google Maps Đường phố
                folium.TileLayer(
                    tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
                    attr="Google",
                    name="Google Maps Đường phố",
                    overlay=False,
                    control=True
                ).add_to(m)

                # Lớp Google Maps Vệ tinh
                folium.TileLayer(
                    tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                    attr="Google",
                    name="Google Maps Vệ tinh",
                    overlay=False,
                    control=True
                ).add_to(m)

                # Định vị GPS vị trí hiện tại
                LocateControl(auto_start=False, flyTo=True).add_to(m)
                folium.LayerControl().add_to(m)

                # Vẽ Tuyến cáp
                path_coords = [hdn_coords[n] for n in node_path if n in hdn_coords]
                if len(path_coords) > 1:
                    folium.PolyLine(path_coords, color="#1e40af", weight=6, opacity=0.85, tooltip="Tuyến cáp").add_to(m)

                # Marker Đầu/Cuối
                if td_a in hdn_coords:
                    folium.Marker(hdn_coords[td_a], popup=f"TĐ A: {td_a}", icon=folium.Icon(color="green")).add_to(m)
                if td_b in hdn_coords:
                    folium.Marker(hdn_coords[td_b], popup=f"TĐ B: {td_b}", icon=folium.Icon(color="black")).add_to(m)

                # Marker Điểm Đứt Cáp
                folium.Marker(
                    [fault_lat, fault_lng],
                    popup=f"Vị trí đứt cáp: {target_dist}m từ {td_a}",
                    icon=folium.Icon(color="red", icon="wrench", prefix="fa")
                ).add_to(m)

                # BẢN ĐỒ FULL VIỀN & CHIỀU CAO LỚN (750px)
                st_folium(m, width="100%", height=750, key="fault_map")
            else:
                st.warning("Thiếu dữ liệu tọa độ Lat/Lng hợp lệ trong sheet HĐN cho đoạn cáp chứa vị trí đứt.")
else:
    st.info("👈 Hãy nhập thông tin điểm A, điểm B và bấm **'Tìm vị trí sự cố'** từ Menu bên trái để hiển thị bản đồ.")
