import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Tìm Vị Trí Sự Cố Cáp", layout="wide")

# 1. Tải và đọc dữ liệu từ file Excel Data.xlsx
@st.cache_data
def load_data():
    file_path = "Data.xlsx"
    df_uplink = pd.read_excel(file_path, sheet_name="Uplink")
    df_doan_cap = pd.read_excel(file_path, sheet_name="Đoạn Cáp")
    df_hdn = pd.read_excel(file_path, sheet_name="HĐN")
    return df_uplink, df_doan_cap, df_hdn

try:
    df_uplink, df_doan_cap, df_hdn = load_data()
except Exception as e:
    st.error(f"Lỗi khi tải file Data.xlsx: {e}")
    st.stop()

st.title("Hệ Thống Xác Định Vị Trí Sự Cố Cáp Trên Bản Đồ")

# 2. Giao diện nhập liệu
col1, col2, col3 = st.columns(3)

with col1:
    td_a = st.text_input("Nhập TĐ A:", value="")
with col2:
    td_b = st.text_input("Nhập TĐ B:", value="")
with col3:
    target_dist = st.number_input("Khoảng cách đo được từ TĐ A (mét):", min_value=0.0, step=1.0)

if st.button("Xác định vị trí"):
    if not td_a or not td_b:
        st.warning("Vui lòng nhập đầy đủ TĐ A và TĐ B!")
    else:
        # 3. Tra cứu tuyến đi trong sheet Uplink
        route_row = df_uplink[(df_uplink['TĐ A'] == td_a) & (df_uplink['TĐ B'] == td_b)]
        
        if route_row.empty:
            st.error(f"Không tìm thấy tuyến đường kết nối trực tiếp từ {td_a} đến {td_b} trong sheet Uplink!")
        else:
            # Lấy danh sách chuỗi các điểm đi qua (ví dụ: TĐ A -> x -> y -> z -> TĐ B)
            nodes = route_row.iloc[0]['Tuyến Đi'].split("->")
            nodes = [n.strip() for n in nodes]
            
            # 4. Tính toán khoảng cách tích lũy dựa vào sheet Đoạn Cáp
            segments = []
            accumulated_dist = 0.0
            found_segment = None
            
            for i in range(len(nodes) - 1):
                node_start = nodes[i]
                node_end = nodes[i+1]
                
                # Tra khoảng cách đoạn cáp giữa node_start và node_end
                cap_row = df_doan_cap[
                    ((df_doan_cap['Điểm Đầu'] == node_start) & (df_doan_cap['Điểm Cuối'] == node_end)) |
                    ((df_doan_cap['Điểm Đầu'] == node_end) & (df_doan_cap['Điểm Cuối'] == node_start))
                ]
                
                if cap_row.empty:
                    st.error(f"Không tìm thấy chiều dài đoạn cáp giữa {node_start} và {node_end} trong sheet Đoạn Cáp!")
                    st.stop()
                
                length = float(cap_row.iloc[0]['Chiều Dài'])
                start_dist = accumulated_dist
                accumulated_dist += length
                
                seg_info = {
                    "start_node": node_start,
                    "end_node": node_end,
                    "length": length,
                    "start_dist": start_dist,
                    "end_dist": accumulated_dist
                }
                segments.append(seg_info)
                
                # Kiểm tra khoảng cách X mét nằm trong đoạn cáp nào
                if start_dist <= target_dist <= accumulated_dist and found_segment is None:
                    found_segment = seg_info

            # 5. So sánh và kiểm tra kết quả
            if target_dist > accumulated_dist:
                st.error(f"Khoảng cách nhập vào ({target_dist}m) vượt quá tổng chiều dài tuyến cáp ({accumulated_dist}m)!")
            elif found_segment:
                st.success(f"Vị trí cần tìm nằm trên đoạn cáp: **{found_segment['start_node']} ➔ {found_segment['end_node']}**")
                
                # Tính tỷ lệ vị trí tương đối trên đoạn cáp chứa điểm sự cố
                offset_in_seg = target_dist - found_segment['start_dist']
                ratio = offset_in_seg / found_segment['length'] if found_segment['length'] > 0 else 0

                # 6. Lấy tọa độ các điểm từ sheet HĐN và nội suy vị trí sự cố
                hdn_dict = df_hdn.set_index('Tên TĐ')[['Kinh Độ', 'Vĩ Độ']].to_dict('index')
                
                # Chuẩn bị danh sách tọa độ để vẽ đường tuyến cáp
                polyline_coords = []
                missing_coords = []
                for node in nodes:
                    if node in hdn_dict:
                        polyline_coords.append((hdn_dict[node]['Vĩ Độ'], hdn_dict[node]['Kinh Độ']))
                    else:
                        missing_coords.append(node)
                
                if missing_coords:
                    st.warning(f"Thiếu tọa độ trong sheet HĐN cho các điểm: {', '.join(missing_coords)}")
                
                p1 = hdn_dict.get(found_segment['start_node'])
                p2 = hdn_dict.get(found_segment['end_node'])
                
                if p1 and p2:
                    # Nội suy tuyến tính tọa độ điểm sự cố
                    target_lat = p1['Vĩ Độ'] + ratio * (p2['Vĩ Độ'] - p1['Vĩ Độ'])
                    target_lon = p1['Kinh Độ'] + ratio * (p2['Kinh Độ'] - p1['Kinh Độ'])
                    
                    # 7. Hiển thị bản đồ với Folium
                    m = folium.Map(location=[target_lat, target_lon], zoom_start=15)
                    
                    # Vẽ tuyến đường cáp
                    if polyline_coords:
                        folium.PolyLine(polyline_coords, color="blue", weight=4, opacity=0.7).add_to(m)
                        for node, coord in zip(nodes, polyline_coords):
                            folium.CircleMarker(
                                location=coord,
                                radius=5,
                                popup=node,
                                color="black",
                                fill=True
                            ).add_to(m)
                    
                    # Marker vị trí sự cố
                    folium.Marker(
                        location=[target_lat, target_lon],
                        popup=f"Vị trí sự cố ({target_dist}m từ {td_a})",
                        icon=folium.Icon(color="red", icon="info-sign")
                    ).add_to(m)
                    
                    st_folium(m, width=900, height=500)
                else:
                    st.error("Không thể xác định tọa độ bản đồ do thiếu dữ liệu tọa độ của đoạn cáp chứa điểm sự cố!")
