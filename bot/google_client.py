""" API-клиент для работы с сервисами Google (в частности: с Google Sheets) """
from time import sleep
from typing import Dict, List, Optional, Union
from googleapiclient.discovery import build, Resource
from google.oauth2 import service_account
import json

SCOPES = (
    'https://www.googleapis.com/auth/spreadsheets',
)

class GoogleAPIClient:
    """ API-клиент для работы с сервисами Google (в частности: с Google Sheets) """

    def __init__(
        self,
        book_id: Optional[str] = None,
        sheet_title: Optional[str] = None,
        sheet_id: str = 0,
        start_col: str = 'A',
        last_col='AY'
    ):
        """
        Args:
            book_id: текстовый идентификатор книги
            sheet_title: название листа
            start_col: колонка, с которой начинаются данные
            last_col: колонка, на которой заканчиваются данные
        """
        # авторизация
        self.sheets_service: Resource = self.__auth()
        self.__book_id = book_id
        self.__sheet_title = sheet_title
        self.__start_col = start_col
        self.__last_col = last_col
        self.sheet_id = sheet_id

    def add_values_from_list(self, values: List, start_row: int, pause: float = .0):
        """ Запись данных на лист с добавлением новой строки перед вставкой

        Args:
            values: данные в виде списка словарей
            start_row: с какой строки начинать запись
        """
        # Сначала добавляем новую строку перед start_row
        insert_body = {
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": self.sheet_id,  # ID листа (не имя)
                            "dimension": "ROWS",
                            "startIndex": start_row - 1,  # где добавить строку
                            "endIndex": start_row  # одна строка
                        },
                        "inheritFromBefore": True  # если True, новая строка будет копировать формат предыдущей
                    }
                }
            ]
        }
        # Выполняем запрос на добавление строки
        self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=self.__book_id,
            body=insert_body
        ).execute()
        # Теперь вставляем значения в добавленную строку
        body = {
            "valueInputOption": "USER_ENTERED",
            "data": [
                {
                    "range": f"{self.__sheet_title}!{self.__start_col}{start_row}",
                    "majorDimension": "ROWS",
                    "values": [values]
                },
            ]
        }
        self.sheets_service.spreadsheets().values().batchUpdate(spreadsheetId=self.__book_id, body=body).execute()
        sleep(pause)

    def get_sheet(self, dictionary: bool = True) -> Union[List[Dict], List[List]]:
        """ Получить данные с листа

        Args:
            dictionary: True - в виде списка словарей

        Returns:
            список словарей или список списков с данными с листа
        """
        res = []
        # Call the Sheets API
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.__book_id,
                range=f'{self.__sheet_title}!A1:{self.__last_col}').execute()
            values = result.get('values', [])
        except Exception as e:
            self.logger.warning(e)
            return res


        if not values:
            return res
        else:
            for row in values:
                res.append(row)
            if dictionary and len(res) > 0:
                d_res = list()
                for r in range(1, len(res)):
                    line = dict()
                    for n, k in enumerate(res[0]):
                        try:
                            line[k] = res[r][n]
                        except:
                            pass
                    d_res.append(line)
                return d_res
        return res

    @staticmethod
    def __auth() -> Resource:
        """ Авторизация (через сервисный аккаунт)

        Returns:
            объект для обращения к гуглу по API
        """
        with open('creds.json','r') as f:
            token = json.load(f)
        
        creds = service_account.Credentials.from_service_account_info(
            token,    # тут чтение из переменной окружения, ожидает словарь
            scopes=SCOPES
        )
        return build('sheets', 'v4', credentials=creds)
