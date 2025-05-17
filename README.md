# Bot for reading club
## using:
- docker-compose
- poetry
- loguru
- aiogram
- openai
- google_api-python-client
- openai

## Preparation
```sh
mkdir bookworm_bot && cd $_
git clone https://github.com/FomenkoKS/bookworm-telegram-bot.git .
cp example.env .env
```

Change .env
=======
Edit .env with your tokens and other information

Download creds of your service account as creds.json (https://cloud.google.com/iam/docs/service-accounts-create)

## Starting
```sh
docker-compose up -d
```
