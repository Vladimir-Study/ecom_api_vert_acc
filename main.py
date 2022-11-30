from flask import Flask
from flask_restx import Api, Resource, reqparse, abort
from flask_jwt_extended import JWTManager, create_access_token  
from datetime import timedelta
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
from pprint import pprint
import psycopg2
import os
import hashlib

load_dotenv()

api = Api()

app = Flask(__name__)
api.init_app(app)
app.config["JWT_SECRET_KEY"] = "super_secret"
jwt = JWTManager(app)

'''
engine = create_engine(f"postgresql+psycopg2")
connection = psycopg2.connect(
    host=os.environ['PG_HOST'],
    port=os.environ['PG_PORT'],
    dbname=os.environ['PG_DB'],
    user=os.environ['PG_USER'],
    password=os.environ['PG_PASSWORD'],
    target_session_attrs=os.environ['TARGET_SESSION_ATTRS'],
    sslmode=os.environ['SSLMODE']
)
'''
def connection():
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT'],
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_LOGIN'],
        password=os.environ['DB_PASSWORD'],
        target_session_attrs=os.environ['TARGET_SESSION_ATTRS'],
        sslmode=os.environ['SSLMODE']
    )
    return conn


@api.route("/add_client", endpoint='add_client')
@api.doc(params={
    'name': 'An Name',
    'login': 'An Login',
    'password': 'An Password'
    })
class ClientAccount(Resource):

    def get_token(self, client_id, expire_time=24):
        expires_delta = timedelta(expire_time)
        token = create_access_token(identity=client_id, expires_delta=expires_delta)
        return token

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str)
        parser.add_argument('login', type=str)
        parser.add_argument('password', type=str)
        args = parser.parse_args()
        conn = connection()
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT id FROM client WHERE login = '{args['login']}'")
                login_in_db = cursor.fetchone()
                if login_in_db is not None:
                    abort(400, "A User with this username exists!")
                password = args['password']
                salt = os.urandom(16)
                key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 10000, dklen=16)
                cursor.execute(f"INSERT INTO client (name, login, pass, active_hex) "
                               f"VALUES ('{args['name']}', '{args['login']}', '{salt.hex()}', '{key.hex()}') "
                               f"RETURNING id")
                client_id = cursor.fetchone()
                conn.commit()
                token = self.get_token(client_id)
                cursor.execute(
                    f"INSERT INTO account_list (mp_id, "
                    f"client_id, name, status_1) "
                    f"VALUES (5, {client_id[0]}, '{args['name']}', 'Active')  "
                    f"RETURNING id;"
                )
                account_id = cursor.fetchone()
                conn.commit()
                cursor.execute(
                    f"INSERT INTO account_service_data "
                    f"(account_id, attribute_id, attribute_value) "
                    f"VALUES ({account_id[0]}, 22, '{token}')"
                )
                conn.commit()
                cursor.execute(
                    f"INSERT INTO account_service_data "
                    f"(account_id, attribute_id, attribute_value) "
                    f"VALUES ({account_id[0]}, 23, '{client_id[0]}')"
                )
                conn.commit()
                return args


if __name__ == "__main__":
    app.run(debug=True, port=3000)