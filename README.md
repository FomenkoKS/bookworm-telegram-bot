# Bot for reading club
## using:
- docker-compose
- poetry
- loguru
- aiogram
<<<<<<< HEAD
- openai
- 
=======
- google_api-python-client
- openai
>>>>>>> fc4d42063324562954cd532b0365a30431b59ea0

## Preparation
```sh
mkdir bookworm_bot && cd $_
git clone https://github.com/FomenkoKS/bookworm-telegram-bot.git .
cp example.env .env
```
<<<<<<< HEAD
Change .env
=======
Edit .env with your tokens and other information
>>>>>>> fc4d42063324562954cd532b0365a30431b59ea0

Download creds of your service account as creds.json (https://cloud.google.com/iam/docs/service-accounts-create)

## Starting
```sh
docker-compose up -d
```
