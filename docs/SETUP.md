# Setup guide: run ShopMart on your own computer

This takes you from an empty computer to a working store site with the AI assistant. Everything runs locally: the language model (Llama 3.2) and the site both stay on your machine, and no account or API key is needed.

Tested on Ubuntu Linux (Docker Engine 29, Compose v5, an NVIDIA GTX 1650 with 4 GB). The Docker steps for Windows and macOS are the standard Docker equivalents and have **not** been tested here. The no-Docker route (section 6) was checked on Ubuntu from a clean copy of the repository.

## 1. What you need

| | Minimum | Notes |
|---|---|---|
| Computer | 8 GB RAM, about 8 GB free disk | The first start downloads about 2.5 GB of models plus Docker images |
| GPU | Optional | An NVIDIA GPU with 4 GB of video memory gave a typical answer in about 4 seconds here (7 seconds for the slowest). On CPU only it is much slower (not measured here, expect tens of seconds) |
| Software | Docker with the Compose plugin, Git | Python is **not** needed for the Docker route (Linux `start.sh` uses `python3` once, to make a password) |
| Phone (optional) | Any phone with a camera | To scan the QR tags. It must be on the same Wi-Fi or hotspot as the computer, or use the public tunnel (section 5) |

## 2. Install Docker

* **Linux:** install Docker Engine and the Compose plugin from <https://docs.docker.com/engine/install/>. Let your user run Docker without `sudo`: `sudo usermod -aG docker $USER`, then log out and in.
* **Windows / macOS:** install Docker Desktop from <https://www.docker.com/products/docker-desktop/>.

Check: `docker compose version` prints a version.

**NVIDIA GPU (optional, much faster):** install the NVIDIA driver and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), then check that Docker can see the GPU:

```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

**No NVIDIA GPU (AMD, Intel, macOS, or just not set up):** open `docker-compose.yml` and delete the whole `deploy:` block under `llm-engine` (the lines from `deploy:` down to `capabilities: [gpu]`). The model then runs on the CPU. Without this edit, Docker stops with `could not select device driver "nvidia"`.

## 3. Get the code and start it

```bash
git clone https://github.com/Sarup-A-K/ShopMart.git
cd ShopMart
```

**Linux:**

```bash
./start.sh
```

It finds the computer's network address, creates a `.env` file with a random admin password on the first run, and starts the containers.

**Windows (PowerShell) or macOS:** `start.sh` only works on Linux, so do its two jobs by hand.

1. Create a file called `.env` in the project folder with one line (choose your own password):
   ```
   ADMIN_PASSWORD=choose-a-password
   ```
   If you skip this, the password is the default `omnitag-admin`. Do not leave the default if other people can reach the site.
2. Find the computer's address on your Wi-Fi (`ipconfig` on Windows, `ipconfig getifaddr en0` on macOS), for example `192.168.1.20`. Then start:
   ```powershell
   $env:PUBLIC_URL = "http://192.168.1.20:8000"    # Windows PowerShell
   docker compose up -d
   ```
   ```bash
   PUBLIC_URL=http://192.168.1.20:8000 docker compose up -d     # macOS / Linux shell
   ```
   `PUBLIC_URL` is the address printed into the QR codes. If you only use the computer itself, you can leave it out.

## 4. Wait for the first start, then open it

The first start downloads the Llama 3.2 model (about 2 GB) and the embedding model `nomic-embed-text` (about 0.3 GB). How long it takes depends on your connection. Follow it:

```bash
docker logs -f local_llm_engine      # stops being busy when both "pull" lines say success
```

Check the site is ready:

```bash
curl http://localhost:8000/api/health
```

You want `"status":"online"` and `"rag":{"ready":true, ...}`. If `ready` is false the embedding model is still downloading; wait a minute and run it again.

Then open:

* **The store:** <http://localhost:8000>
* **The admin page:** <http://localhost:8000/admin>. The password is the `ADMIN_PASSWORD` line in `.env`.
* **From a phone:** the address `start.sh` printed (for example `http://192.168.43.10:8000`), with the phone on the same Wi-Fi or hotspot.

Quick check that the AI works: open any product and ask "Is this a good deal?". The first answer after starting is slow (the model loads into memory); later ones are quicker. A "✓ Checked against store data" line under the answer means the fact-check ran.

Notes:
* The 19 sample products appear on the first start (`seed_products.json`). The database `omnitag.db` is created in the project folder. Delete it and restart to reset every price.
* The product photos are **not** in the repository (they belong to their brands). Without them each product shows a generated, clearly labelled illustration card. Add your own in Admin → Photos.

## 5. Optional: scan QR tags with a phone

1. On the admin page open **QR tags**. The first tag is the **Master QR** (put it at the entrance); the rest are one per shelf. No tag carries a price.
2. Print the page or show it on the screen, and scan it with the phone's own camera app. It opens the product page.
3. The tags contain the computer's address. If the address changes (new Wi-Fi, new hotspot), run `./start.sh` again and reprint the tags.
4. The **in-page camera scanner** needs an `https://` address. On Linux, `./start.sh --tunnel` opens a free public https address through Cloudflare and prints it. While it runs, anyone with the link can use the site, so close it when you are done: `docker rm -f omnitag_tunnel`. The README explains how to get a fixed address on your own domain.

For a recorded demo, follow [`DEMO_GUIDE.md`](DEMO_GUIDE.md) (every question in it has been run on this system).

## 6. Without Docker (Linux or macOS)

Use this if Docker is not an option, or on a Mac where you want the model to use the Apple GPU through the native Ollama app.

```bash
# 1. Ollama from https://ollama.com/download, then:
ollama pull llama3.2
ollama pull nomic-embed-text

# 2. Python 3.10+ (on Ubuntu/Debian first: sudo apt install python3-venv)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run
export OLLAMA_BASE_URL=http://localhost:11434
export ADMIN_PASSWORD=choose-a-password
export PUBLIC_URL=http://<this-computer's-address>:8000      # optional, for QR codes
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. Other settings, all optional: `LLM_MODEL` (default `llama3.2`), `EMBED_MODEL` (default `nomic-embed-text`), `DB_PATH` (default `omnitag.db`).

## 7. Tests and the evaluation

```bash
# Unit tests (guardrails and the fact-check)
docker exec -w /workspace local_web_app python -m unittest discover -s tests -v

# Evaluation (about 25 minutes; keep other GPU work closed). See the README, "Evaluation"
docker exec -w /workspace local_web_app python eval/run_eval.py --quick
```

The evaluation needs the evaluation-only switches on (`OMNITAG_TEST_HOOKS=1`) and must be turned off afterwards; the README has the exact commands. Do not run it while recording a demo, because both use the same GPU.

## 8. Stopping and cleaning up

```bash
docker compose down            # stop everything, keep the models and your data
docker compose down -v         # also delete the downloaded models (about 2.5 GB; they download again next time)
docker rm -f omnitag_tunnel    # close the public tunnel, if you opened one
```

## 9. When something goes wrong

| Symptom | Cause and fix |
|---|---|
| `could not select device driver "nvidia"` | No NVIDIA GPU or toolkit. Delete the `deploy:` block (section 2) and run `docker compose up -d` again |
| `permission denied` talking to Docker (Linux) | Add yourself to the docker group (section 2) and log in again, or put `sudo` in front |
| The first answer takes minutes, or the chat says the model is not ready | The models are still downloading. Check `docker logs local_llm_engine` |
| `/api/health` shows `"rag":{"ready":false}` | The embedding model is not downloaded yet. Wait, then `docker restart local_web_app` |
| Answers are always very slow | Probably running on the CPU. Check the GPU setup (section 2) and `docker logs local_llm_engine`, which says what it found when it "discovers available GPUs" |
| Port 8000 or 11434 is already in use | Stop the other program, or change the left-hand number in `ports:` in `docker-compose.yml` |
| The phone cannot open the address | Same Wi-Fi or hotspot? Campus and guest Wi-Fi often isolate devices from each other: use the phone's hotspot. A computer firewall may block port 8000 |
| The QR code opens the wrong address | The address changed. Run `./start.sh` again (or set `PUBLIC_URL` and restart) and reprint the tags |
| The in-page camera scanner will not start | It needs `https://` (section 5). The phone's own camera app always works |
| `python3 -m venv` fails on Ubuntu | `sudo apt install python3-venv` |
| Forgot the admin password | `grep ADMIN_PASSWORD .env` |
| The site shows old prices after you change data | Prices come from `omnitag.db`. Edit them in the admin page; deleting `omnitag.db` resets everything to the sample data |

## 10. What you just started

* `llm-engine`: Ollama, serving `llama3.2` (answers) and `nomic-embed-text` (search by meaning).
* `web-app`: FastAPI serving the pages, the API, the AI pipeline and the admin page, plus a SQLite database.

How the pipeline works (retrieval, tool calling, guardrails, fact-check) is explained in [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md). The problems met while building it, and the fixes, are in [`FINDINGS.md`](FINDINGS.md).
