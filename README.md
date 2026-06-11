# hxwl-61204

Python Django后端：小型实验室冰箱样本格位。

## Port

61204

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver 0.0.0.0:61204
```

## API

- `GET /health/`
- `POST /samples/`
- `GET /samples/`
- `PATCH /samples/{sample_id}/move/`
- `PATCH /samples/{sample_id}/checkout/`
- `GET /slots/`
- `GET /owners/{owner}/samples/`
