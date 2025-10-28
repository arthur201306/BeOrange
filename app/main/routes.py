from flask import Flask, render_template, request, redirect, url_for, session, Blueprint, jsonify
from .. import supabase

main_bp = Blueprint('main', __name__, template_folder='templates')


@main_bp.route('/')
def main():
    return render_template("/index.html")

@main_bp.route('/login', methods['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("/login.html")