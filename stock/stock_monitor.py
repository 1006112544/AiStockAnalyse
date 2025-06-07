import tkinter as tk
from tkinter import ttk
import akshare as ak
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
from datetime import datetime, timedelta
import threading
import time
import matplotlib
import queue
import concurrent.futures
matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 设置中文字体
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

class StockMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("股票监控")
        
        # 设置窗口大小
        window_width = 1920
        window_height = 1200
        
        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 计算窗口位置
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # 设置窗口大小和位置
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 创建主框架
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建输入框和按钮
        self.input_frame = ttk.Frame(self.main_frame)
        self.input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.input_frame, text="股票代码:").pack(side=tk.LEFT)
        self.stock_code = ttk.Entry(self.input_frame, width=10)
        self.stock_code.pack(side=tk.LEFT, padx=5)
        self.stock_code.insert(0, "000001")  # 默认股票代码
        
        # 添加查询按钮
        ttk.Button(self.input_frame, text="查询", command=self.query_stock).pack(side=tk.LEFT, padx=5)
        
        # 创建K线类型选择
        self.k_type = tk.StringVar(value="日K")
        ttk.Radiobutton(self.input_frame, text="日K", variable=self.k_type, value="日K", command=self.on_k_type_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.input_frame, text="周K", variable=self.k_type, value="周K", command=self.on_k_type_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.input_frame, text="月K", variable=self.k_type, value="月K", command=self.on_k_type_change).pack(side=tk.LEFT, padx=5)
        
        # 创建数据范围输入框
        self.range_frame = ttk.Frame(self.input_frame)
        self.range_frame.pack(side=tk.LEFT, padx=10)
        
        # 日K数据范围
        self.daily_range_label = ttk.Label(self.range_frame, text="日K范围(月):")
        self.daily_range = ttk.Entry(self.range_frame, width=5)
        self.daily_range.insert(0, "24")  # 默认24个月
        
        # 周K数据范围
        self.weekly_range_label = ttk.Label(self.range_frame, text="周K范围(年):")
        self.weekly_range = ttk.Entry(self.range_frame, width=5)
        self.weekly_range.insert(0, "10")  # 默认10年
        
        # 月K数据范围
        self.monthly_range_label = ttk.Label(self.range_frame, text="月K范围(年):")
        self.monthly_range = ttk.Entry(self.range_frame, width=5)
        self.monthly_range.insert(0, "20")  # 默认20年
        
        # 创建均线控制按钮
        self.show_ma = tk.BooleanVar(value=True)
        self.ma_checkbutton = ttk.Checkbutton(self.input_frame, text="显示均线", variable=self.show_ma, command=self.update_chart)
        self.ma_checkbutton.pack(side=tk.LEFT, padx=5)
        
        # 初始化显示日K的范围输入框
        self.update_range_input_visibility()
        
        # 创建信息显示区域
        self.info_frame = ttk.Frame(self.main_frame)
        self.info_frame.pack(fill=tk.X, pady=5)
        
        self.info_labels = {}
        info_items = ["股票名称", "股票代码", "当前价格", "涨跌比例", "市值", "动态市盈率", "静态市盈率", "换手率", "开盘价", "最低价", "最高价"]
        for i, item in enumerate(info_items):
            ttk.Label(self.info_frame, text=f"{item}:").grid(row=0, column=i*2, padx=5)
            self.info_labels[item] = ttk.Label(self.info_frame, text="--")
            self.info_labels[item].grid(row=0, column=i*2+1, padx=5)
        
        # 创建图表区域
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3, 1]}, figsize=(12, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 添加缩放功能
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
        # 初始化变量
        self.is_trading_day = self.is_trading_day_check()
        self.has_queried = False
        self.current_data = None  # 存储当前数据
        self.k_line_data = {}     # 存储不同K线类型的数据
        
        # 创建线程池和请求队列
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self.request_queue = queue.Queue()
        self.current_request = None
        self.request_lock = threading.Lock()
        
        # 初始化图表
        self.clear_chart()
    
    def clear_chart(self):
        """清空图表显示"""
        self.ax1.clear()
        self.ax2.clear()
        self.ax1.set_title("请输入股票代码并点击查询")
        self.ax1.grid(True)
        self.ax2.grid(True)
        self.canvas.draw()
    
    def query_stock(self):
        """查询股票数据"""
        # 清空当前显示
        self.show_error("正在获取数据...")
        
        # 更新股票信息
        self.update_stock_info()
        
        # 获取所有K线类型的数据
        self.fetch_all_k_line_data()
        
        # 标记已经查询过
        self.has_queried = True
        
        # 更新当前K线类型的图表
        self.update_chart()
    
    def fetch_all_k_line_data(self):
        """获取所有K线类型的数据"""
        try:
            stock_code = self.stock_code.get()
            end_date = datetime.now().strftime('%Y%m%d')
            
            # 获取日K数据
            try:
                daily_months = int(self.daily_range.get())
                if daily_months < 1:
                    daily_months = 24  # 如果输入无效，使用默认值
            except ValueError:
                daily_months = 24
            start_date = (datetime.now() - timedelta(days=daily_months*30)).strftime('%Y%m%d')
            future = self.fetch_data_async(ak.stock_zh_a_hist, 
                                         symbol=stock_code, 
                                         period="daily", 
                                         adjust="qfq", 
                                         start_date=start_date, 
                                         end_date=end_date)
            self.k_line_data["日K"] = future.result(timeout=10)
            
            # 获取周K数据
            try:
                weekly_years = int(self.weekly_range.get())
                if weekly_years < 1:
                    weekly_years = 10  # 如果输入无效，使用默认值
            except ValueError:
                weekly_years = 10
            start_date = (datetime.now() - timedelta(days=weekly_years*365)).strftime('%Y%m%d')
            future = self.fetch_data_async(ak.stock_zh_a_hist, 
                                         symbol=stock_code, 
                                         period="weekly", 
                                         adjust="qfq", 
                                         start_date=start_date, 
                                         end_date=end_date)
            self.k_line_data["周K"] = future.result(timeout=10)
            
            # 获取月K数据
            try:
                monthly_years = int(self.monthly_range.get())
                if monthly_years < 1:
                    monthly_years = 20  # 如果输入无效，使用默认值
            except ValueError:
                monthly_years = 20
            start_date = (datetime.now() - timedelta(days=monthly_years*365)).strftime('%Y%m%d')
            future = self.fetch_data_async(ak.stock_zh_a_hist, 
                                         symbol=stock_code, 
                                         period="monthly", 
                                         adjust="qfq", 
                                         start_date=start_date, 
                                         end_date=end_date)
            self.k_line_data["月K"] = future.result(timeout=10)
            
        except Exception as e:
            print(f"Error fetching K-line data: {e}")
            self.show_error("获取K线数据失败")
    
    def cancel_current_request(self):
        """取消当前正在进行的网络请求"""
        with self.request_lock:
            if self.current_request and not self.current_request.done():
                self.current_request.cancel()
                self.current_request = None
    
    def fetch_data_async(self, func, *args, **kwargs):
        """异步获取数据"""
        self.cancel_current_request()  # 取消之前的请求
        with self.request_lock:
            self.current_request = self.executor.submit(func, *args, **kwargs)
            return self.current_request
    
    def is_trading_day_check(self):
        try:
            # 获取交易日历
            trade_cal = ak.tool_trade_date_hist_sina()
            today = datetime.now().strftime('%Y-%m-%d')
            return today in trade_cal['trade_date'].values
        except:
            return True  # 如果获取失败，默认认为是交易日
    
    def get_last_trading_day_data(self, stock_code):
        try:
            # 获取日K数据
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            # 获取最近一个交易日的数据
            return df.iloc[0]
        except:
            return None
    
    def calculate_ma(self, df, periods=[5, 10, 20, 30]):
        ma_data = {}
        for period in periods:
            ma_data[f'MA{period}'] = df['收盘'].rolling(window=period).mean()
        return ma_data
    
    def on_k_type_change(self):
        """处理K线类型切换"""
        # 更新范围输入框的可见性
        self.update_range_input_visibility()
        
        if not self.has_queried:
            return  # 如果还没有查询过，不执行任何操作
            
        # 更新图表显示
        self.update_chart()
    
    def update_stock_info(self):
        """更新股票信息"""
        try:
            stock_code = self.stock_code.get()
            stock_info = None

            # 尝试使用 stock_zh_a_spot_em 获取实时数据
            try:
                print(f"Attempting to fetch stock info from stock_zh_a_spot_em for {stock_code}")
                future = self.fetch_data_async(ak.stock_zh_a_spot_em)
                df = future.result(timeout=60)  # 增加超时时间到60秒
                stock_info = df[df['代码'] == stock_code].iloc[0]
                print(f"Successfully fetched stock info from stock_zh_a_spot_em for {stock_code}")
            except Exception as e:
                print(f"Error fetching stock info from stock_zh_a_spot_em for {stock_code}: {e}")

            # 如果 stock_zh_a_spot_em 失败，尝试使用 stock_individual_info_em
            if stock_info is None:
                try:
                    print(f"Attempting to fetch stock info from stock_individual_info_em for {stock_code}")
                    future = self.fetch_data_async(ak.stock_individual_info_em, symbol=stock_code)
                    df = future.result(timeout=60)  # 增加超时时间到60秒
                    stock_info = df.iloc[0]
                    # 将 stock_individual_info_em 返回的数据转换为与 stock_zh_a_spot_em 相同的格式
                    stock_info = {
                        '名称': stock_info['股票简称'],
                        '代码': stock_code,
                        '最新价': stock_info['最新价'],
                        '涨跌幅': stock_info['涨跌幅'],
                        '总市值': stock_info['总市值'],
                        '市盈率': stock_info['市盈率-动态'],
                        '市盈率-动态': stock_info['市盈率-动态'],
                        '换手率': stock_info['换手率'],
                        '开盘': stock_info['开盘'],
                        '最低': stock_info['最低'],
                        '最高': stock_info['最高']
                    }
                    print(f"Successfully fetched stock info from stock_individual_info_em for {stock_code}")
                except Exception as e:
                    print(f"Error fetching stock info from stock_individual_info_em for {stock_code}: {e}")

            # 如果 stock_individual_info_em 也失败，尝试使用 stock_zh_a_hist 获取最新交易日数据
            if stock_info is None:
                try:
                    print(f"Attempting to fetch stock info from stock_zh_a_hist for {stock_code}")
                    future = self.fetch_data_async(ak.stock_zh_a_hist, symbol=stock_code, period="daily", adjust="qfq")
                    df = future.result(timeout=60)  # 增加超时时间到60秒
                    latest_data = df.iloc[0]
                    stock_info = {
                        '名称': stock_code,  # 无法获取名称，使用代码代替
                        '代码': stock_code,
                        '最新价': latest_data['收盘'],
                        '涨跌幅': latest_data['涨跌幅'],
                        '总市值': 'N/A',  # 无法获取总市值
                        '市盈率': 'N/A',  # 无法获取市盈率
                        '市盈率-动态': 'N/A',
                        '换手率': 'N/A',  # 无法获取换手率
                        '开盘': latest_data['开盘'],
                        '最低': latest_data['最低'],
                        '最高': latest_data['最高']
                    }
                    print(f"Successfully fetched stock info from stock_zh_a_hist for {stock_code}")
                except Exception as e:
                    print(f"Error fetching stock info from stock_zh_a_hist for {stock_code}: {e}")

            # 如果所有方法都失败，抛出异常
            if stock_info is None:
                raise Exception("All stock info fetch methods failed")

            # 在主线程中更新UI
            self.root.after(0, lambda: self.update_info_display(stock_info))
            
        except Exception as e:
            print(f"Error updating stock info: {e}")
            # 显示错误信息
            self.root.after(0, lambda: self.show_error("获取股票信息失败"))
    
    def show_error(self, message):
        """显示错误信息"""
        for label in self.info_labels.values():
            label.config(text="--")
        self.info_labels["股票名称"].config(text=message)
    
    def update_info_display(self, stock_info):
        """更新信息显示"""
        try:
            # 更新基本信息
            self.info_labels["股票名称"].config(text=stock_info['名称'])
            self.info_labels["股票代码"].config(text=stock_info['代码'])
            
            # 更新价格信息（带颜色）
            current_price = float(stock_info['最新价'])
            change_ratio = float(stock_info['涨跌幅'])
            
            # 设置价格颜色
            price_color = 'red' if change_ratio >= 0 else 'green'
            self.info_labels["当前价格"].config(text=f"{current_price:.2f}", foreground=price_color)
            self.info_labels["涨跌比例"].config(text=f"{change_ratio:.2f}%", foreground=price_color)
            
            # 更新其他信息
            self.info_labels["市值"].config(text=f"{float(stock_info['总市值'])/100000000:.2f}亿")
            self.info_labels["动态市盈率"].config(text=f"{float(stock_info['市盈率']):.2f}")
            self.info_labels["静态市盈率"].config(text=f"{float(stock_info['市盈率-动态']):.2f}")
            self.info_labels["换手率"].config(text=f"{float(stock_info['换手率']):.2f}%")
            
            # 更新开盘、最低、最高价
            self.info_labels["开盘价"].config(text=f"{float(stock_info['开盘']):.2f}")
            self.info_labels["最低价"].config(text=f"{float(stock_info['最低']):.2f}")
            self.info_labels["最高价"].config(text=f"{float(stock_info['最高']):.2f}")
            
        except Exception as e:
            print(f"Error updating info display: {e}")
            self.show_error("更新显示信息失败")
    
    def get_time_range_limits(self, k_type):
        """获取不同K线类型的时间范围限制"""
        now = datetime.now()
        if k_type == "日K":
            max_range = (now - timedelta(days=5*365))  # 5年
            min_range = (now - timedelta(days=30))     # 1个月
        elif k_type == "周K":
            max_range = (now - timedelta(days=20*365)) # 20年
            min_range = (now - timedelta(days=90))     # 3个月
        else:  # 月K
            max_range = (now - timedelta(days=20*365)) # 20年
            min_range = (now - timedelta(days=365))    # 1年
        return max_range, min_range

    def on_scroll(self, event):
        if event.inaxes == self.ax1 or event.inaxes == self.ax2:
            if self.current_data is None:
                return
                
            # 获取当前x轴范围
            cur_xlim = self.ax1.get_xlim()
            
            # 计算缩放比例
            base_scale = 1.1
            scale = base_scale if event.button == 'up' else 1/base_scale
            
            # 计算新的范围
            new_width = (cur_xlim[1] - cur_xlim[0]) / scale
            
            # 获取数据范围
            data_xlim = self.ax1.get_xlim()
            
            # 获取当前K线类型的时间范围限制
            k_type = self.k_type.get()
            max_range, min_range = self.get_time_range_limits(k_type)
            
            # 限制最小缩放（根据K线类型限制最小时间范围）
            min_width = (data_xlim[1] - max_range.timestamp())
            if new_width < min_width:
                return
            
            # 限制最大缩放（根据K线类型限制最大时间范围）
            max_width = (data_xlim[1] - min_range.timestamp())
            if new_width > max_width:
                return
            
            # 获取鼠标位置对应的数据坐标
            if event.inaxes == self.ax1:
                xdata = event.xdata
            else:
                # 如果是在成交量图表上，需要转换坐标
                xdata = self.ax1.transData.inverted().transform(
                    self.ax2.transData.transform((event.xdata, 0)))[0]
            
            # 计算新的中心点
            relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
            
            # 计算新的范围
            new_xlim = [xdata - new_width*(1-relx), xdata + new_width*relx]
            
            # 确保不超出数据范围
            new_xlim[0] = max(new_xlim[0], data_xlim[0])
            new_xlim[1] = min(new_xlim[1], data_xlim[1])
            
            # 设置新的范围
            self.ax1.set_xlim(new_xlim)
            
            # 同步更新成交量图表的x轴范围
            self.ax2.set_xlim(new_xlim)
            
            # 重绘图表
            self.canvas.draw()

    def update_chart(self):
        """更新图表"""
        if not self.has_queried:
            return  # 如果还没有查询过，不执行任何操作
            
        try:
            k_type = self.k_type.get()
            
            # 从已获取的数据中获取当前K线类型的数据
            if k_type not in self.k_line_data:
                return
                
            df = self.k_line_data[k_type]
            date_col = '日期'
            price_col = '收盘'
            volume_col = '成交量'
            open_col = '开盘'
            close_col = '收盘'
            high_col = '最高'
            low_col = '最低'
            
            # 在主线程中更新图表
            self.root.after(0, lambda: self.update_chart_display(df, date_col, price_col, volume_col, open_col, close_col, high_col, low_col, k_type))
            
        except Exception as e:
            print(f"Error updating chart: {e}")
    
    def update_chart_display(self, df, date_col, price_col, volume_col, open_col, close_col, high_col, low_col, k_type):
        """在主线程中更新图表显示"""
        try:
            # 存储当前数据
            self.current_data = df
            
            # 清除旧图
            self.ax1.clear()
            self.ax2.clear()
            
            # 绘制K线图
            for i in range(len(df)):
                if df[close_col].iloc[i] >= df[open_col].iloc[i]:
                    color = 'red'  # 上涨为红色
                else:
                    color = 'green'  # 下跌为绿色
                
                # 绘制上下引线
                self.ax1.plot([df[date_col].iloc[i], df[date_col].iloc[i]], 
                            [df[low_col].iloc[i], df[high_col].iloc[i]], 
                            color=color, linewidth=1)
                
                # 绘制K线实体
                self.ax1.plot([df[date_col].iloc[i], df[date_col].iloc[i]], 
                            [df[open_col].iloc[i], df[close_col].iloc[i]], 
                            color=color, linewidth=3)
                
                # 绘制成交量
                self.ax2.bar(df[date_col].iloc[i], df[volume_col].iloc[i], 
                            color=color, width=0.6, label='成交量' if i == 0 else "")
            
            # 找出最高点和最低点
            max_high = df[high_col].max()
            min_low = df[low_col].min()
            max_high_date = df[date_col][df[high_col] == max_high].iloc[0]
            min_low_date = df[date_col][df[low_col] == min_low].iloc[0]
            
            # 在最高点添加标记
            self.ax1.plot(max_high_date, max_high, 'r^', markersize=10, label='最高点')
            self.ax1.annotate(f'最高: {max_high:.2f}', 
                            xy=(max_high_date, max_high),
                            xytext=(10, 10), textcoords='offset points',
                            color='red', fontsize=8)
            
            # 在最低点添加标记
            self.ax1.plot(min_low_date, min_low, 'gv', markersize=10, label='最低点')
            self.ax1.annotate(f'最低: {min_low:.2f}', 
                            xy=(min_low_date, min_low),
                            xytext=(10, -15), textcoords='offset points',
                            color='green', fontsize=8)
            
            if self.show_ma.get():
                # 计算并绘制均线
                ma_data = self.calculate_ma(df)
                colors = ['gray', 'purple', 'yellow', 'blue']  # 5日、10日、20日、30日均线颜色
                for (ma_name, ma_values), color in zip(ma_data.items(), colors):
                    self.ax1.plot(df[date_col], ma_values, color=color, label=ma_name, linewidth=1)
            
            self.ax1.set_title(f'{k_type}价格走势')
            self.ax1.grid(True)
            self.ax1.legend()
            
            self.ax2.set_title(f'{k_type}成交量')
            self.ax2.grid(True)
            # 只在有成交量数据时显示图例
            if len(df) > 0:
                self.ax2.legend()
            
            # 设置初始显示范围（显示所有数据）
            self.ax1.set_xlim(df[date_col].iloc[0], df[date_col].iloc[-1])
            self.ax2.set_xlim(df[date_col].iloc[0], df[date_col].iloc[-1])
            
            # 调整布局，确保x轴标签不被截断
            plt.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating chart display: {e}")
    
    def update_range_input_visibility(self):
        """更新范围输入框的可见性"""
        k_type = self.k_type.get()
        
        # 隐藏所有范围输入框
        self.daily_range_label.pack_forget()
        self.daily_range.pack_forget()
        self.weekly_range_label.pack_forget()
        self.weekly_range.pack_forget()
        self.monthly_range_label.pack_forget()
        self.monthly_range.pack_forget()
        
        # 显示当前K线类型的范围输入框
        if k_type == "日K":
            self.daily_range_label.pack(side=tk.LEFT)
            self.daily_range.pack(side=tk.LEFT, padx=2)
        elif k_type == "周K":
            self.weekly_range_label.pack(side=tk.LEFT)
            self.weekly_range.pack(side=tk.LEFT, padx=2)
        elif k_type == "月K":
            self.monthly_range_label.pack(side=tk.LEFT)
            self.monthly_range.pack(side=tk.LEFT, padx=2)

    def __del__(self):
        """清理资源"""
        self.executor.shutdown(wait=False)

if __name__ == "__main__":
    root = tk.Tk()
    app = StockMonitor(root)
    root.mainloop() 