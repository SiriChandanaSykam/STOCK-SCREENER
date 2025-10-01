import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_tv_chart(df, symbol):
    colors = {
        'bg': '#131722', 'up': '#26a69a', 'down': '#ef5350', 'sma20': '#2196f3', 'sma50': '#ff9800',
        'macd': '#4caf50', 'signal': '#f44336', 'rsi': '#00bcd4', 'grid': '#363a45', 'text': '#d1d4dc'
    }
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.5, 0.15, 0.2, 0.15],
        subplot_titles=[f"{symbol} Price", "RSI", "MACD", "Volume"]
    )
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        increasing_line_color=colors['up'],
        decreasing_line_color=colors['down'],
        name='OHLC'), row=1, col=1)
    # SMA20, SMA50 overlays if present
    for ma_name, color in [('SMA20', colors['sma20']), ('SMA50', colors['sma50'])]:
        if ma_name in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[ma_name], name=ma_name, line=dict(color=color, width=2)), row=1, col=1)

    # RSI
    if 'RSI' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color=colors['rsi'], width=2)), row=2, col=1)
        fig.add_hline(y=70, line=dict(color=colors['down'], dash='dash'), row=2, col=1)
        fig.add_hline(y=30, line=dict(color=colors['up'], dash='dash'), row=2, col=1)

    # MACD + Signal
    if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color=colors['macd'], width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], name='Signal', line=dict(color=colors['signal'], width=2)), row=3, col=1)

    # Volume bars
    volume_colors = [colors['up'] if df['Close'].iloc[i] >= df['Open'].iloc[i] else colors['down'] for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=volume_colors, name='Volume'), row=4, col=1)

    fig.update_layout(
        height=900, paper_bgcolor=colors['bg'], plot_bgcolor=colors['bg'],
        font=dict(color=colors['text'], family="Trebuchet MS"),
        legend=dict(orientation='h', y=1.02, x=1, bgcolor='rgba(0,0,0,0)')
    )
    for i in range(1,5):
        fig.update_xaxes(showgrid=True, gridcolor=colors['grid'], row=i, col=1)
        fig.update_yaxes(showgrid=True, gridcolor=colors['grid'], row=i, col=1)
    fig.update_xaxes(rangeslider_visible=False)

    return fig
 
