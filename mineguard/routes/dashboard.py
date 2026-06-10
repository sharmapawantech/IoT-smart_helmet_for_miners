from flask import Blueprint, render_template
from flask_login import login_required

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    return render_template('dashboard.html')


@dashboard_bp.route('/history')
@login_required
def history():
    return render_template('history.html')


@dashboard_bp.route('/alerts')
@login_required
def alerts():
    return render_template('alerts.html')
