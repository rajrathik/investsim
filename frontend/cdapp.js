/**
 * CD Portfolio Advisor - Frontend Application
 */

const API_BASE_URL = 'http://localhost:5000/api';

// DOM Elements
const form = document.getElementById('investment-form');
const loadingEl = document.getElementById('loading');
const errorMessageEl = document.getElementById('error-message');
const errorTextEl = document.getElementById('error-text');
const resultsEl = document.getElementById('results');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    form.addEventListener('submit', handleFormSubmit);
    checkBackendHealth();
});

/**
 * Check if backend is running
 */
async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        console.log('Backend status:', data);
    } catch (error) {
        console.warn('Backend not yet available:', error.message);
    }
}

/**
 * Handle form submission
 */
async function handleFormSubmit(e) {
    e.preventDefault();
    
    // Get form values
    const investmentAmount = parseFloat(document.getElementById('investment-amount').value);
    const userInput = document.getElementById('user-input').value;
    
    // Validate
    if (investmentAmount < 1000) {
        showError('Investment amount must be at least $1,000');
        return;
    }
    
    if (!userInput.trim()) {
        showError('Please describe your investment goals');
        return;
    }
    
    // Show loading, hide error and results
    showLoading();
    hideError();
    hideResults();
    
    try {
        // Call API
        const response = await fetch(`${API_BASE_URL}/recommend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                investment_amount: investmentAmount,
                user_input: userInput
            })
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Hide loading
        hideLoading();
        
        // Display results
        displayResults(data);
        
        // Smooth scroll to results
        setTimeout(() => {
            resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
        
    } catch (error) {
        hideLoading();
        showError(`Failed to get recommendations: ${error.message}. Please ensure the backend server is running.`);
        console.error('Error:', error);
    }
}

/**
 * Display results
 */
function displayResults(data) {
    // Display preferences
    displayPreferences(data.preferences);
    
    // Display market sentiment
    displayMarketSentiment(data.market_sentiment);
    
    // Display portfolios
    displayPortfolio('user-need', data.portfolio_user_need);
    displayPortfolio('with-market', data.portfolio_with_market);
    
    // Display differences
    displayDifferences(data);
    
    // Show results section
    showResults();
}

/**
 * Display user preferences
 */
function displayPreferences(preferences) {
    const grid = document.getElementById('preferences-grid');
    
    const preferenceItems = [
        {
            icon: '🎯',
            label: 'Investment Goal',
            value: preferences.goal
        },
        {
            icon: '⏱️',
            label: 'Time Horizon',
            value: preferences.time_horizon
        },
        {
            icon: '📊',
            label: 'Risk Tolerance',
            value: preferences.risk_tolerance
        },
        {
            icon: '💧',
            label: 'Liquidity Need',
            value: preferences.liquidity_need
        }
    ];
    
    grid.innerHTML = preferenceItems.map(item => `
        <div class="preference-item">
            <div class="preference-icon">${item.icon}</div>
            <div class="preference-label">${item.label}</div>
            <div class="preference-value">${item.value.replace(/_/g, ' ')}</div>
        </div>
    `).join('');
    
    // Add investor profile if available
    if (preferences.investor_profile) {
        grid.innerHTML += `
            <div class="preference-item" style="grid-column: 1 / -1;">
                <div class="preference-icon">👤</div>
                <div class="preference-label">Investor Profile</div>
                <div class="preference-value" style="font-size: 0.95rem;">${preferences.investor_profile}</div>
            </div>
        `;
    }
}

/**
 * Display market sentiment
 */
function displayMarketSentiment(sentiment) {
    const badgeEl = document.getElementById('sentiment-badge');
    const contentEl = document.getElementById('market-content');
    
    // Determine sentiment class
    let sentimentClass = 'sentiment-stable';
    let sentimentIcon = '📊';
    let sentimentText = 'Stable';
    
    if (sentiment.rate_direction.includes('declining')) {
        sentimentClass = 'sentiment-declining';
        sentimentIcon = '📉';
        sentimentText = 'Rates Declining';
    } else if (sentiment.rate_direction.includes('rising')) {
        sentimentClass = 'sentiment-rising';
        sentimentIcon = '📈';
        sentimentText = 'Rates Rising';
    }
    
    badgeEl.className = `sentiment-badge ${sentimentClass}`;
    badgeEl.innerHTML = `${sentimentIcon} ${sentimentText}`;
    
    contentEl.innerHTML = `
        <div class="market-recommendation">${sentiment.recommendation}</div>
        <div class="market-rationale">${sentiment.rationale}</div>
    `;
}

/**
 * Display portfolio
 */
function displayPortfolio(type, portfolioData) {
    const summaryEl = document.getElementById(`summary-${type}`);
    const explanationEl = document.getElementById(`explanation-${type}`);
    const cdsEl = document.getElementById(`cds-${type}`);
    
    if (!portfolioData || !portfolioData.cds || portfolioData.cds.length === 0) {
        summaryEl.innerHTML = '<p>No portfolio available</p>';
        explanationEl.innerHTML = '';
        cdsEl.innerHTML = '';
        return;
    }
    
    const summary = portfolioData.summary;
    const cds = portfolioData.cds;
    const explanation = portfolioData.explanation || '';
    
    // Display summary
    summaryEl.innerHTML = `
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-label">Investment</div>
                <div class="summary-value">${formatCurrency(summary.total_investment)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Avg. APY</div>
                <div class="summary-value">${summary.average_apy}%</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Interest Earned</div>
                <div class="summary-value">${formatCurrency(summary.total_interest)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Avg. Maturity</div>
                <div class="summary-value">${summary.weighted_avg_maturity} mo</div>
            </div>
        </div>
        <div class="summary-highlight">
            <div class="summary-highlight-value">${formatCurrency(summary.total_maturity_value)}</div>
            <div class="summary-highlight-label">Total at Maturity</div>
        </div>
    `;
    
    // Display AI explanation
    if (explanation) {
        // Convert line breaks to paragraphs
        const paragraphs = explanation.split('\n\n').filter(p => p.trim());
        explanationEl.innerHTML = paragraphs.map(p => `<p>${p.trim()}</p>`).join('');
    } else {
        explanationEl.innerHTML = '';
    }
    
    // Display CDs
    cdsEl.innerHTML = cds.map(cd => `
        <div class="cd-item">
            <div class="cd-header">
                <div class="cd-name">${cd.cd_name} (${cd.maturity_months} months)</div>
                <div class="cd-apy">${cd.apy}%</div>
            </div>
            <div class="cd-details">
                <div class="cd-detail">
                    <div class="cd-detail-label">Investment</div>
                    <div class="cd-detail-value">${formatCurrency(cd.investment_amount)}</div>
                </div>
                <div class="cd-detail">
                    <div class="cd-detail-label">APR</div>
                    <div class="cd-detail-value">${cd.apr}%</div>
                </div>
                <div class="cd-detail">
                    <div class="cd-detail-label">Interest Earned</div>
                    <div class="cd-detail-value">${formatCurrency(cd.total_interest)}</div>
                </div>
                <div class="cd-detail">
                    <div class="cd-detail-label">Term</div>
                    <div class="cd-detail-value">${formatMonths(cd.maturity_months)}</div>
                </div>
            </div>
            <div class="cd-maturity">
                <div class="maturity-date">Matures: ${formatDate(cd.maturity_date)}</div>
                <div class="maturity-value">${formatCurrency(cd.maturity_value)}</div>
            </div>
        </div>
    `).join('');
}

/**
 * Display differences between portfolios
 */
function displayDifferences(data) {
    const differencesEl = document.getElementById('differences-grid');
    
    const userNeed = data.portfolio_user_need.summary;
    const withMarket = data.portfolio_with_market.summary;
    const sentiment = data.market_sentiment;
    
    const differences = [
        {
            title: '🎯 Option 1: Your Needs Focus',
            text: `This portfolio is designed purely based on your stated preferences - ${data.preferences.time_horizon} time horizon with ${data.preferences.risk_tolerance} risk tolerance. It focuses on meeting your ${data.preferences.goal} goals without considering external market factors.`
        },
        {
            title: '📈 Option 2: Market-Optimized',
            text: `This strategy incorporates current market conditions (${sentiment.rate_direction.replace('_', ' ')}) to potentially maximize returns. ${sentiment.recommendation}`
        },
        {
            title: '💰 Return Comparison',
            text: `Option 1 generates ${formatCurrency(userNeed.total_interest)} in interest, while Option 2 generates ${formatCurrency(withMarket.total_interest)} - a difference of ${formatCurrency(Math.abs(withMarket.total_interest - userNeed.total_interest))}.`
        },
        {
            title: '⏰ Timeline Difference',
            text: `Option 1 has a weighted average maturity of ${userNeed.weighted_avg_maturity} months, while Option 2 averages ${withMarket.weighted_avg_maturity} months. This affects when you'll have access to your funds.`
        }
    ];
    
    differencesEl.innerHTML = differences.map(diff => `
        <div class="difference-item">
            <div class="difference-title">${diff.title}</div>
            <div class="difference-text">${diff.text}</div>
        </div>
    `).join('');
}

/**
 * Utility functions
 */
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatMonths(months) {
    if (months < 12) {
        return `${months} months`;
    }
    const years = Math.floor(months / 12);
    const remainingMonths = months % 12;
    if (remainingMonths === 0) {
        return `${years} ${years === 1 ? 'year' : 'years'}`;
    }
    return `${years}y ${remainingMonths}m`;
}

/**
 * UI state management
 */
function showLoading() {
    loadingEl.classList.remove('hidden');
}

function hideLoading() {
    loadingEl.classList.add('hidden');
}

function showError(message) {
    errorTextEl.textContent = message;
    errorMessageEl.classList.remove('hidden');
}

function hideError() {
    errorMessageEl.classList.add('hidden');
}

function showResults() {
    resultsEl.classList.remove('hidden');
}

function hideResults() {
    resultsEl.classList.add('hidden');
}
