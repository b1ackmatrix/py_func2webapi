#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time : 2017/5/29 2:22
# @Author : BlackMatrix
# @Site : https://github.com/blackmatrix7
# @File : models.py
# @Software: PyCharm
from ..oauth.models import Client
from app.database import ModelBase, ModelMixin, db
from werkzeug.security import check_password_hash, generate_password_hash


class User(ModelBase, ModelMixin):

    __tablename__ = 'user'

    email = db.Column(db.String(100), nullable=False)
    user_name = db.Column(db.String(40), nullable=True)
    password_hash = db.Column(db.String(200))

    clients = db.relationship(Client, backref='user', lazy='dynamic', order_by=Client.id)

    @classmethod
    def get_by_email(cls, email):
        return db.session.query(cls).filter(cls.email == email).first()

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, value):
        self.password_hash = generate_password_hash(password=value)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)



