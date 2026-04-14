# Deploy Cloud

## Cách nhanh nhất: Docker

Build image:
```bash
docker build -t ainhandien-api .
```

Run local:
```bash
docker run --rm -p 8000:8000 ainhandien-api
```

Mở:
```text
http://localhost:8000
```

## Deploy lên Render / Railway / VPS

### Start command
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Environment variables
- `PORT`: cổng cloud cấp cho app.
- `MACHINE_ACCESS_KEYS`: mapping JSON `machine_id -> secret` nếu muốn bật auth theo máy.

Ví dụ:
```json
{"camera-01":"key-abc","camera-02":"key-def"}
```

### Lưu ý
- Thư mục `runs/` nên là volume/persistent storage nếu muốn giữ ảnh history sau khi restart.
- File model `yolov8n.pt` phải có trong image hoặc volume.
- Nếu muốn truy cập API từ Flutter/mobile, dùng URL public của cloud service.

## Header khi gọi API

Nếu bật machine auth:
- `X-Machine-Id: camera-01`
- `X-Machine-Key: key-abc`

## Endpoint kiểm tra

```text
GET /
GET /health
```

## Deploy lên Azure for Students

Khuyến nghị dùng **Ubuntu VM + Docker** để app ML của bạn chạy ổn định hơn các gói free web service.

### 1. Tạo tài nguyên
- Vào Azure Portal.
- Tạo `Resource Group` mới.
- Tạo `Virtual Machine`:
	- Image: `Ubuntu 22.04 LTS`
	- Size: chọn VM nhỏ nhưng đủ RAM, tối thiểu nên 2 vCPU / 4 GB RAM nếu có thể.
	- Authentication: SSH key.
	- Public inbound ports: bật `22` và `80`.

### 2. Cài Docker trên VM
SSH vào VM rồi chạy:
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
	"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
	$(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
	sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Đăng xuất rồi SSH lại để group `docker` có hiệu lực.

### 3. Lấy code và build image
```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>
docker build -t ainhandien-api .
```

### 4. Chạy container
```bash
docker run -d \
	--name ainhandien-api \
	--restart unless-stopped \
	-p 80:8000 \
	-e MACHINE_ACCESS_KEYS='{"camera-01":"key-abc"}' \
	-v $(pwd)/runs:/app/runs \
	ainhandien-api
```

Nếu muốn không bật machine auth trong giai đoạn test, bỏ `-e MACHINE_ACCESS_KEYS=...`.

### 5. Mở firewall
- Trong Azure Network Security Group, đảm bảo inbound port `80` đã mở.
- Nếu dùng reverse proxy sau này thì có thể chỉ mở `80` và `443`.

### 6. URL truy cập
- API: `http://<public-ip>/`
- Health check: `http://<public-ip>/health`

### 7. Lưu ý cho app này
- Nên giữ `runs/` dưới dạng volume để ảnh history không mất khi restart.
- File model `yolov8n.pt` đã nằm trong repo nên sẽ đi theo image.
- Nếu VM yếu, lần khởi động đầu có thể chậm vì tải thư viện ML.

### 8. Cập nhật code sau này
```bash
git pull
docker build -t ainhandien-api .
docker stop ainhandien-api
docker rm ainhandien-api
docker run -d \
	--name ainhandien-api \
	--restart unless-stopped \
	-p 80:8000 \
	-v $(pwd)/runs:/app/runs \
	ainhandien-api
```

## Tự động deploy từ GitHub lên Azure VM

Bạn có thể dùng workflow GitHub Actions ở `.github/workflows/deploy-azure.yml` để mỗi lần push lên `main` thì Azure VM tự pull code và restart container.

### Cần tạo GitHub Secrets
- `AZURE_HOST`: public IP hoặc domain của VM.
- `AZURE_USER`: user SSH, ví dụ `azureuser`.
- `AZURE_SSH_KEY`: private key SSH dùng để đăng nhập VM.
- `AZURE_APP_DIR`: đường dẫn code trên VM, ví dụ `/home/azureuser/ainhandien`.
- `AZURE_REPO_URL`: URL repo GitHub, ví dụ `https://github.com/<user>/<repo>.git`.
- `AZURE_MACHINE_ACCESS_KEYS`: JSON mapping nếu bạn bật auth theo máy.

### Cách dùng
1. Đảm bảo VM đã cài Docker và đã mở port `80`.
2. Add các secrets ở GitHub repo: `Settings -> Secrets and variables -> Actions`.
3. Push code lên `main`.
4. Workflow sẽ SSH vào VM, `git reset --hard`, build image và chạy lại container.

### Lưu ý
- Nếu repo private, nên set `AZURE_REPO_URL` bằng URL có quyền truy cập phù hợp hoặc dùng repo public.
- File `runs/` vẫn nên là volume để ảnh history không mất sau khi deploy.