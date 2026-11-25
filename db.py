import pymysql

def get_db_connection():
    connection = pymysql.connect(
        host="localhost",
        user="root",
        password="Bhagat@2005",
        database="rag_assistant",
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection