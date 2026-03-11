"""
CD Portfolio Recommendation Engine - Backend API
Flask server providing CD portfolio recommendations
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import pyodbc
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# Database configuration
DB_CONFIG = {
    'server': 's1',
    'database': 'd1',
    'username': 'su1',
    'password': 'p1'
}

class CDPortfolioEngine:
    """CD Portfolio recommendation engine"""
    
    def __init__(self):
        self.cd_data = None
        self.load_cd_data()
    
    def get_db_connection(self):
        """Create database connection"""
        conn_str = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={DB_CONFIG["server"]};'
            f'DATABASE={DB_CONFIG["database"]};'
            f'UID={DB_CONFIG["username"]};'
            f'PWD={DB_CONFIG["password"]}'
        )
        return pyodbc.connect(conn_str)
    
    def load_cd_data(self):
        """Load CD data from SQL Server or CSV fallback"""
        try:
            conn = self.get_db_connection()
            query = "SELECT * FROM dbo.cdavailable"
            self.cd_data = pd.read_sql(query, conn)
            conn.close()
            print(f"✓ Loaded {len(self.cd_data)} CDs from database")
        except Exception as e:
            print(f"⚠ Database connection failed: {e}")
            print("⚠ Attempting to load from CSV...")
            try:
                self.cd_data = pd.read_csv('cd_rates.csv')
                print(f"✓ Loaded {len(self.cd_data)} CDs from CSV")
            except:
                print("✗ Failed to load CD data")
                self.cd_data = pd.DataFrame()
    
    def parse_investment_needs(self, user_input, investment_amount):
        """Parse natural language input to extract investment preferences"""
        
        user_input_lower = user_input.lower()
        
        # Default preferences
        preferences = {
            'risk_tolerance': 'moderate',
            'time_horizon': 'medium',
            'goal': 'growth',
            'liquidity_need': 'low'
        }
        
        # Risk tolerance
        if any(word in user_input_lower for word in ['conservative', 'safe', 'low risk', 'secure', 'protect']):
            preferences['risk_tolerance'] = 'conservative'
        elif any(word in user_input_lower for word in ['aggressive', 'high return', 'maximum', 'growth']):
            preferences['risk_tolerance'] = 'aggressive'
        
        # Time horizon
        if any(word in user_input_lower for word in ['short', 'soon', 'quickly', 'emergency', '6 month', '1 year']):
            preferences['time_horizon'] = 'short'
        elif any(word in user_input_lower for word in ['long', 'retire', 'years', 'decade', '5 year', '10 year']):
            preferences['time_horizon'] = 'long'
        
        # Goals
        if any(word in user_input_lower for word in ['retire', 'retirement', 'pension']):
            preferences['goal'] = 'retirement'
        elif any(word in user_input_lower for word in ['education', 'college', 'school']):
            preferences['goal'] = 'education'
        elif any(word in user_input_lower for word in ['house', 'home', 'down payment']):
            preferences['goal'] = 'home'
        elif any(word in user_input_lower for word in ['emergency', 'rainy day', 'backup']):
            preferences['goal'] = 'emergency'
        
        # Liquidity needs
        if any(word in user_input_lower for word in ['access', 'liquid', 'flexible', 'available']):
            preferences['liquidity_need'] = 'high'
        
        return preferences
    
    def get_market_sentiment(self):
        """Simulate market sentiment analysis"""
        
        # In production, this would call real market data APIs
        # For now, simulating based on current economic indicators
        
        sentiment = {
            'rate_direction': 'stable_to_declining',  # 'rising', 'stable', 'declining', 'stable_to_declining'
            'confidence': 0.7,
            'recommendation': 'Consider locking in current rates with medium-term CDs',
            'rationale': 'Fed signals potential rate cuts in 2025-2026. Current rates near peak.'
        }
        
        return sentiment
    
    def recommend_portfolio_user_need(self, preferences, investment_amount):
        """Generate portfolio based purely on user needs"""
        
        if self.cd_data.empty:
            return None
        
        # Filter based on preferences
        time_horizon = preferences['time_horizon']
        risk_tolerance = preferences['risk_tolerance']
        
        # Define maturity ranges based on time horizon
        if time_horizon == 'short':
            maturity_range = (1, 12)
            target_maturities = [3, 6, 9]
        elif time_horizon == 'long':
            maturity_range = (36, 120)
            target_maturities = [36, 60, 84, 96]
        else:  # medium
            maturity_range = (12, 48)
            target_maturities = [12, 18, 24, 36]
        
        # Filter CDs in range
        filtered_cds = self.cd_data[
            (self.cd_data['Maturity_Months'] >= maturity_range[0]) &
            (self.cd_data['Maturity_Months'] <= maturity_range[1])
        ].copy()
        
        # Select diversified CDs
        portfolio = self.build_laddered_portfolio(
            filtered_cds, 
            target_maturities, 
            investment_amount,
            risk_tolerance
        )
        
        return portfolio
    
    def recommend_portfolio_with_market(self, preferences, investment_amount, market_sentiment):
        """Generate portfolio incorporating market sentiment"""
        
        if self.cd_data.empty:
            return None
        
        time_horizon = preferences['time_horizon']
        risk_tolerance = preferences['risk_tolerance']
        rate_direction = market_sentiment['rate_direction']
        
        # Adjust strategy based on market sentiment
        if 'declining' in rate_direction:
            # Rates expected to fall - favor longer terms to lock in
            if time_horizon == 'short':
                maturity_range = (6, 24)
                target_maturities = [9, 12, 18, 24]
            elif time_horizon == 'long':
                maturity_range = (48, 120)
                target_maturities = [60, 72, 84, 96]
            else:
                maturity_range = (18, 60)
                target_maturities = [24, 36, 48, 60]
        
        elif rate_direction == 'rising':
            # Rates expected to rise - favor shorter terms for flexibility
            if time_horizon == 'short':
                maturity_range = (1, 9)
                target_maturities = [3, 6, 9]
            elif time_horizon == 'long':
                maturity_range = (12, 48)
                target_maturities = [12, 24, 36, 48]
            else:
                maturity_range = (6, 24)
                target_maturities = [9, 12, 18, 24]
        
        else:  # stable
            # Balanced approach
            if time_horizon == 'short':
                maturity_range = (3, 12)
                target_maturities = [3, 6, 9, 12]
            elif time_horizon == 'long':
                maturity_range = (36, 96)
                target_maturities = [36, 60, 72, 84]
            else:
                maturity_range = (12, 48)
                target_maturities = [12, 24, 36, 48]
        
        # Filter CDs
        filtered_cds = self.cd_data[
            (self.cd_data['Maturity_Months'] >= maturity_range[0]) &
            (self.cd_data['Maturity_Months'] <= maturity_range[1])
        ].copy()
        
        # Build portfolio
        portfolio = self.build_laddered_portfolio(
            filtered_cds,
            target_maturities,
            investment_amount,
            risk_tolerance
        )
        
        return portfolio
    
    def build_laddered_portfolio(self, filtered_cds, target_maturities, investment_amount, risk_tolerance):
        """Build a laddered CD portfolio"""
        
        portfolio = []
        num_cds = min(5, len(target_maturities))
        allocation_per_cd = investment_amount / num_cds
        
        selected_maturities = []
        
        for target_maturity in target_maturities[:num_cds]:
            # Find best CD near target maturity
            filtered_cds['maturity_diff'] = abs(filtered_cds['Maturity_Months'] - target_maturity)
            
            # Exclude already selected maturities
            available_cds = filtered_cds[~filtered_cds['Maturity_Months'].isin(selected_maturities)]
            
            if len(available_cds) == 0:
                continue
            
            # Sort by APY (higher is better) and proximity to target
            available_cds = available_cds.sort_values(
                by=['APY', 'maturity_diff'],
                ascending=[False, True]
            )
            
            best_cd = available_cds.iloc[0]
            selected_maturities.append(best_cd['Maturity_Months'])
            
            # Calculate returns
            years = best_cd['Maturity_Months'] / 12
            maturity_value = allocation_per_cd * pow(1 + best_cd['APY']/100, years)
            total_interest = maturity_value - allocation_per_cd
            
            portfolio.append({
                'cd_name': best_cd['CD_Name'],
                'maturity_months': int(best_cd['Maturity_Months']),
                'apr': float(best_cd['APR']),
                'apy': float(best_cd['APY']),
                'investment_amount': round(allocation_per_cd, 2),
                'maturity_value': round(maturity_value, 2),
                'total_interest': round(total_interest, 2),
                'maturity_date': self.calculate_maturity_date(int(best_cd['Maturity_Months']))
            })
        
        return portfolio
    
    def calculate_maturity_date(self, months):
        """Calculate maturity date"""
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta
        
        maturity = datetime.now() + relativedelta(months=months)
        return maturity.strftime('%Y-%m-%d')

# Initialize engine
engine = CDPortfolioEngine()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'cd_data_loaded': not engine.cd_data.empty,
        'total_cds': len(engine.cd_data)
    })

@app.route('/api/recommend', methods=['POST'])
def recommend_portfolio():
    """Main recommendation endpoint"""
    
    try:
        data = request.json
        user_input = data.get('user_input', '')
        investment_amount = float(data.get('investment_amount', 10000))
        
        # Parse user needs
        preferences = engine.parse_investment_needs(user_input, investment_amount)
        
        # Get market sentiment
        market_sentiment = engine.get_market_sentiment()
        
        # Generate both portfolios
        portfolio_user_need = engine.recommend_portfolio_user_need(preferences, investment_amount)
        portfolio_with_market = engine.recommend_portfolio_with_market(
            preferences, 
            investment_amount, 
            market_sentiment
        )
        
        # Calculate portfolio summaries
        def calculate_summary(portfolio):
            if not portfolio:
                return None
            
            total_investment = sum(cd['investment_amount'] for cd in portfolio)
            total_maturity = sum(cd['maturity_value'] for cd in portfolio)
            total_interest = total_maturity - total_investment
            avg_apy = sum(cd['apy'] * cd['investment_amount'] for cd in portfolio) / total_investment
            weighted_months = sum(cd['maturity_months'] * cd['investment_amount'] for cd in portfolio) / total_investment
            
            return {
                'total_investment': round(total_investment, 2),
                'total_maturity_value': round(total_maturity, 2),
                'total_interest': round(total_interest, 2),
                'average_apy': round(avg_apy, 2),
                'weighted_avg_maturity': round(weighted_months, 1),
                'num_cds': len(portfolio)
            }
        
        response = {
            'preferences': preferences,
            'market_sentiment': market_sentiment,
            'portfolio_user_need': {
                'cds': portfolio_user_need,
                'summary': calculate_summary(portfolio_user_need)
            },
            'portfolio_with_market': {
                'cds': portfolio_with_market,
                'summary': calculate_summary(portfolio_with_market)
            }
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cd-data', methods=['GET'])
def get_cd_data():
    """Get all CD data"""
    try:
        cds = engine.cd_data.to_dict('records')
        return jsonify({'cds': cds, 'total': len(cds)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("CD Portfolio Recommendation Engine - Backend API")
    print("=" * 60)
    print(f"Server starting on http://localhost:5000")
    print(f"CDs loaded: {len(engine.cd_data)}")
    print("=" * 60)
    app.run(debug=True, port=5000)
