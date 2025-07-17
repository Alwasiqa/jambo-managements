"""
Blueprint registration
"""

from flask import Blueprint
from . import jambos, orders, parties, production, reports, stock

def register_blueprints(app):
    """Register all blueprints"""
    # Register core blueprints
    app.register_blueprint(jambos.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(parties.bp, url_prefix='/parties')  # Add explicit url_prefix
    app.register_blueprint(production.bp)
    app.register_blueprint(reports.bp, url_prefix='/reports')  # Add explicit url_prefix for reports
    app.register_blueprint(stock.bp, url_prefix='/stock')  # Add stock management blueprint 