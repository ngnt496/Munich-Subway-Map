# Munich U-Bahn Shortest Route

Ung dung tim tuyen U-Bahn giua 2 diem duoc chon tren ban do Munich va so sanh A* voi Dijkstra.

Project chi xu ly U-Bahn/subway tu du lieu OpenStreetMap. Ket qua hien tai toi uu theo chi phi co trong so:

```text
2.5 * (di bo tu diem dau den ga len tau + di bo tu ga xuong tau den diem cuoi) + di U-Bahn
```

Moi chang di bo toi da mac dinh la 2500m. Cach tinh nay tranh viec ket qua "ngan nhat" bi bien thanh tuyen gan nhu toan di bo. Project khong tinh lich tau, thoi gian cho, chuyen tuyen, gia ve, hay thoi gian di thuc te.

## Cai dat

```bash
pip install -r requirements.txt
```

## Tai du lieu cache

Lan dau chay nen preload du lieu OpenStreetMap:

```bash
python preload_data.py
```

Script nay tao cac file trong thu muc `cache/`, gom walk graph, subway graph, cache nhanh `.pkl` va danh sach ga U-Bahn.

## Chay ung dung

```bash
python main.py
```

Tren ban do:

1. Click chuot phai de chon diem bat dau.
2. Click chuot phai de chon diem ket thuc.
3. Chon `A*` hoac `Dijkstra`.
4. Bam `Find Route`.

De so sanh 2 thuat toan, chay cung mot cap diem voi `Dijkstra`, ghi lai distance/nodes/time, sau do doi sang `A*` va chay lai.

## Thuat toan

Ung dung xet tat ca cap ga U-Bahn hop le, tinh chi phi `2.5 * walk + subway`, roi chon cap co chi phi nho nhat. Sau khi chon cap ga tot nhat, app dung thuat toan dang chon trong UI de dung lai 3 doan duong va ve route len ban do.
