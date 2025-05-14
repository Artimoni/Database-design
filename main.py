import os
import sqlite3
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from datetime import datetime
import hashlib

# --- Конфигурация ---
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")
CSV_FILES = {
    "categories": os.path.join(BASE_DIR, "categories.csv"),
    "products": os.path.join(BASE_DIR, "products.csv"),
    "customers": os.path.join(BASE_DIR, "customers.csv"),
    "employees": os.path.join(BASE_DIR, "employees.csv"),
}
DISCOUNT = 0.1  # 10% скидка


# --- Инициализация БД ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY,
            login TEXT UNIQUE,
            password_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY, 
            name TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            price REAL,
            stock INTEGER,
            category_id INTEGER,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY, 
            name TEXT, 
            phone TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY, 
            name TEXT, 
            role TEXT
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY,
            datetime TEXT,
            customer_id INTEGER,
            employee_id INTEGER,
            total_amount REAL
        );
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY,
            sale_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price REAL
        );
    """)
    conn.commit()

    # Создание администратора по умолчанию
    if not conn.execute("SELECT * FROM admins").fetchall():
        default_password = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute(
            "INSERT INTO admins (login, password_hash) VALUES (?, ?)",
            ("admin", default_password)
        )
        conn.commit()

    # Импорт данных из CSV
    for table, path in CSV_FILES.items():
        if os.path.exists(path):
            df = pd.read_csv(path)
            df.to_sql(table, conn, if_exists="replace", index=False)
    conn.close()


init_db()


# --- Вспомогательные функции ---
def get_products():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT id, name, price, stock, category_id FROM products"
        ).fetchall()


def get_customers():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT id, name FROM customers").fetchall()


def get_employees():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT id, name, role FROM employees").fetchall()


def make_sale(product_id, quantity, customer_id, employee_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT price, stock FROM products WHERE id=?", (product_id,))
        price, stock = c.fetchone()
        if stock < quantity:
            raise Exception("Недостаточно товара на складе")
        total = price * quantity * (1 - DISCOUNT)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO sales (datetime, customer_id, employee_id, total_amount) VALUES (?, ?, ?, ?)",
            (now, customer_id, employee_id, total)
        )
        sale_id = c.lastrowid
        c.execute(
            "INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            (sale_id, product_id, quantity, price)
        )
        c.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (quantity, product_id)
        )
        conn.commit()
        return sale_id


# --- Окно чека ---
def show_receipt(sale_id):
    win = tb.Toplevel()
    win.title(f"Чек №{sale_id}")
    win.geometry("500x600")

    with sqlite3.connect(DB_PATH) as conn:
        sale_info = conn.execute("""
            SELECT s.datetime, s.total_amount, c.name, e.name
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            JOIN employees e ON s.employee_id = e.id
            WHERE s.id = ?
        """, (sale_id,)).fetchone()

        items = conn.execute("""
            SELECT p.name, si.quantity, si.price, (si.quantity * si.price) as total
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = ?
        """, (sale_id,)).fetchall()

    datetime_str, total_amount, customer_name, employee_name = sale_info

    receipt_text = f"""
    Чек №{sale_id}
    Дата: {datetime_str}
    Покупатель: {customer_name}
    Сотрудник: {employee_name}
    -------------------------------
    Товары:
    """
    for item in items:
        name, qty, price, total = item
        receipt_text += f"{name} x{qty} @{price:.2f}₽ = {total:.2f}₽\n"

    receipt_text += f"""
    -------------------------------
    Итого: {total_amount:.2f}₽
    Скидка: {DISCOUNT * 100}%
    """

    text_widget = tk.Text(win, font=("Courier New", 12))
    text_widget.insert(tk.END, receipt_text)
    text_widget.pack(fill="both", expand=True, padx=10, pady=10)

    def save_receipt():
        filename = f"Чек_{sale_id}_{datetime_str.replace(':', '-')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(receipt_text)
        messagebox.showinfo("Сохранено", f"Чек сохранён как {filename}")

    ttk.Button(win, text="Сохранить чек", command=save_receipt).pack(pady=10)


# --- Окно продажи ---
def sale_window():
    win = tb.Toplevel()
    win.title("Продажа товара")
    win.geometry("500x450")

    # Элементы формы
    ttk.Label(win, text="Покупатель:").pack(anchor="w", padx=10, pady=(10, 0))
    custs = get_customers()
    cust_var = tk.StringVar()
    cust_cb = ttk.Combobox(win, textvariable=cust_var, values=[f"{c[0]} – {c[1]}" for c in custs])
    cust_cb.pack(fill="x", padx=10)

    ttk.Label(win, text="Сотрудник:").pack(anchor="w", padx=10, pady=(10, 0))
    emps = get_employees()
    emp_var = tk.StringVar()
    emp_cb = ttk.Combobox(win, textvariable=emp_var, values=[f"{e[0]} – {e[1]} ({e[2]})" for e in emps])
    emp_cb.pack(fill="x", padx=10)

    ttk.Label(win, text="Товар:").pack(anchor="w", padx=10, pady=(10, 0))
    prods = get_products()
    prod_var = tk.StringVar()
    prod_cb = ttk.Combobox(win, textvariable=prod_var, values=[f"{p[0]} – {p[1]} (ост. {p[3]})" for p in prods])
    prod_cb.pack(fill="x", padx=10)

    ttk.Label(win, text="Количество:").pack(anchor="w", padx=10, pady=(10, 0))
    qty_var = tk.IntVar(value=1)
    qty_entry = ttk.Entry(win, textvariable=qty_var)
    qty_entry.pack(fill="x", padx=10)

    check_lbl = ttk.Label(win, text="Предварительный чек: 0.00₽", font=("Segoe UI", 12))
    check_lbl.pack(pady=15)

    # Обработчики событий
    def update_check(event=None):
        try:
            pid = int(prod_var.get().split("–")[0].strip())
            qty = qty_var.get()
            price = next(p[2] for p in prods if p[0] == pid)
            total = price * qty * (1 - DISCOUNT)
            check_lbl.config(text=f"Предварительный чек: {total:.2f}₽")
        except:
            check_lbl.config(text="Предварительный чек: 0.00₽")

    prod_cb.bind("<<ComboboxSelected>>", update_check)
    qty_entry.bind("<KeyRelease>", update_check)

    def process_sale():
        try:
            cid = int(cust_var.get().split("–")[0].strip())
            eid = int(emp_var.get().split("–")[0].strip())
            pid = int(prod_var.get().split("–")[0].strip())
            qty = qty_var.get()
            sale_id = make_sale(pid, qty, cid, eid)
            win.destroy()
            show_receipt(sale_id)
        except Exception as ex:
            messagebox.showerror("Ошибка", str(ex))

    ttk.Button(win, text="Оформить продажу", command=process_sale).pack(pady=10)


# --- Окно добавления покупателя ---
def add_customer_window():
    win = tb.Toplevel()
    win.title("Новый покупатель")
    win.geometry("450x250")

    ttk.Label(win, text="Имя:").pack(anchor="w", padx=10, pady=(10, 0))
    name_var = tk.StringVar()
    ttk.Entry(win, textvariable=name_var).pack(fill="x", padx=10)

    ttk.Label(win, text="Телефон:").pack(anchor="w", padx=10, pady=(10, 0))
    phone_var = tk.StringVar()
    ttk.Entry(win, textvariable=phone_var).pack(fill="x", padx=10)

    def save_customer():
        if not name_var.get() or not phone_var.get():
            messagebox.showerror("Ошибка", "Все поля обязательны для заполнения")
            return
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO customers (name, phone) VALUES (?, ?)",
                    (name_var.get(), phone_var.get())
                )
                conn.commit()
            messagebox.showinfo("Успех", "Покупатель добавлен")
            win.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Такой телефон уже существует")

    ttk.Button(win, text="Сохранить", command=save_customer).pack(pady=10)


# --- Авторизация администратора ---
def restock_auth_window():
    login_win = tb.Toplevel()
    login_win.title("Авторизация администратора")
    login_win.geometry("350x200")

    ttk.Label(login_win, text="Логин:").pack(anchor="w", padx=10, pady=(5, 0))
    login_var = tk.StringVar()
    ttk.Entry(login_win, textvariable=login_var).pack(fill="x", padx=10)

    ttk.Label(login_win, text="Пароль:").pack(anchor="w", padx=10, pady=(5, 0))
    pass_var = tk.StringVar()
    ttk.Entry(login_win, textvariable=pass_var, show="*").pack(fill="x", padx=10)

    def check_auth():
        with sqlite3.connect(DB_PATH) as conn:
            admin = conn.execute(
                "SELECT password_hash FROM admins WHERE login = ?",
                (login_var.get(),)
            ).fetchone()

        if not admin:
            messagebox.showerror("Ошибка", "Неверный логин")
            return

        input_hash = hashlib.sha256(pass_var.get().encode()).hexdigest()
        if input_hash == admin[0]:
            login_win.destroy()
            restock_window()
        else:
            messagebox.showerror("Ошибка", "Неверный пароль")

    ttk.Button(login_win, text="Войти", command=check_auth).pack(pady=10)


# --- Окно управления запасами ---
def restock_window():
    win = tb.Toplevel()
    win.title("Остатки и пополнение")
    win.geometry("650x450")

    cols = ("ID", "Название", "Остаток")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=10)
    for c in cols:
        tree.heading(c, text=c)
    tree.pack(fill="both", expand=True, padx=10, pady=(10, 0))

    prods = get_products()
    for p in prods:
        tag = "low" if p[3] < 5 else ""
        tree.insert("", "end", values=(p[0], p[1], p[3]), tags=(tag,))
    tree.tag_configure("low", background="#ffd6d6")

    qty_var = tk.IntVar(value=5)
    frm = ttk.Frame(win)
    frm.pack(pady=10)
    ttk.Label(frm, text="Кол-во для пополнения:").grid(row=0, column=0)
    ttk.Entry(frm, textvariable=qty_var, width=5).grid(row=0, column=1, padx=5)

    def order():
        sel = tree.selection()
        if not sel:
            return
        pid = int(tree.item(sel[0])["values"][0])
        q = qty_var.get()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (q, pid))
            conn.commit()
        messagebox.showinfo("OK", f"ID {pid} пополнен на {q} шт.")
        win.destroy()
        restock_window()

    ttk.Button(frm, text="Заказать на склад", command=order).grid(row=0, column=2, padx=10)


# --- История продаж ---
def sales_history_window():
    win = tb.Toplevel()
    win.title("История продаж")
    win.geometry("1000x700")

    cols = ("ID", "Дата", "Сумма", "Покупатель", "Сотрудник")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=20)
    for col in cols:
        tree.heading(col, text=col)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    with sqlite3.connect(DB_PATH) as conn:
        sales = conn.execute("""
            SELECT s.id, s.datetime, s.total_amount, c.name, e.name
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            JOIN employees e ON s.employee_id = e.id
            ORDER BY s.datetime DESC
        """).fetchall()

    for sale in sales:
        tree.insert("", "end", values=sale)

    def on_double_click(event):
        item = tree.selection()[0]
        sale_id = tree.item(item, "values")[0]
        show_receipt(sale_id)

    tree.bind("<Double-1>", on_double_click)


# --- Отчёты и аналитика ---
def report_window():
    win = tb.Toplevel()
    win.title("Расширенные отчёты")
    win.geometry("1200x900")

    notebook = ttk.Notebook(win)
    notebook.pack(fill='both', expand=True, padx=10, pady=10)

    # Вкладка 1: Премия за период
    premium_frame = ttk.Frame(notebook)
    notebook.add(premium_frame, text="Премия за период")

    # Выбор периода
    period_frame = ttk.Frame(premium_frame)
    period_frame.pack(pady=15, fill='x')

    # Месяц
    ttk.Label(period_frame, text="Месяц:", font=('Segoe UI', 10)).grid(row=0, column=0, padx=5)
    month_var = tk.IntVar(value=datetime.now().month)
    month_combo = ttk.Combobox(
        period_frame,
        textvariable=month_var,
        values=list(range(1, 13)),
        state='readonly',
        width=5
    )
    month_combo.grid(row=0, column=1, padx=5)
    month_combo.current(datetime.now().month - 1)

    # Год
    ttk.Label(period_frame, text="Год:", font=('Segoe UI', 10)).grid(row=0, column=2, padx=5)
    year_var = tk.IntVar()

    with sqlite3.connect(DB_PATH) as conn:
        years = conn.execute("""
            SELECT DISTINCT strftime('%Y', datetime) 
            FROM sales 
            ORDER BY datetime DESC
        """).fetchall()

    year_values = [int(y[0]) for y in years] if years else [datetime.now().year]
    year_combo = ttk.Combobox(
        period_frame,
        textvariable=year_var,
        values=year_values,
        state='readonly',
        width=8
    )
    year_combo.grid(row=0, column=3, padx=5)
    year_combo.current(0)

    # Кнопка обновления
    ttk.Button(
        period_frame,
        text="Обновить отчеты",
        command=lambda: update_all_reports(month_var.get(), year_var.get()),
        style='primary.TButton'
    ).grid(row=0, column=4, padx=10)

    # Результаты премии
    result_frame = ttk.Frame(premium_frame)
    result_frame.pack(pady=15, fill='both', expand=True)

    best_employee_label = ttk.Label(
        result_frame,
        text="Лучший сотрудник:",
        font=('Segoe UI', 12, 'bold'),
        anchor='center'
    )
    best_employee_label.pack(pady=10)

    sales_tree = ttk.Treeview(
        result_frame,
        columns=('Сотрудник', 'Продажи', 'Выручка', 'Средний чек'),
        show='headings',
        height=8
    )

    for col in sales_tree['columns']:
        sales_tree.heading(col, text=col)
        sales_tree.column(col, width=150, anchor='e' if col != 'Сотрудник' else 'w')
    sales_tree.pack(fill='both', expand=True, padx=20)

    # Вкладка 2: Общая статистика
    stats_frame = ttk.Frame(notebook)
    notebook.add(stats_frame, text="Общая статистика")

    # Топы
    tops_frame = ttk.Frame(stats_frame)
    tops_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Топ продавцов
    ttk.Label(tops_frame, text="Топ продавцов", font=('Segoe UI', 12, 'bold')).grid(row=0, column=0, padx=5)
    top_sellers = ttk.Treeview(
        tops_frame,
        columns=('Сотрудник', 'Выручка'),
        show='headings',
        height=5
    )
    top_sellers.heading('Сотрудник', text='Сотрудник')
    top_sellers.heading('Выручка', text='Выручка')
    top_sellers.grid(row=1, column=0, padx=5, sticky='nsew')

    # Топ покупателей
    ttk.Label(tops_frame, text="Топ покупателей", font=('Segoe UI', 12, 'bold')).grid(row=0, column=1, padx=5)
    top_customers = ttk.Treeview(
        tops_frame,
        columns=('Покупатель', 'Потрачено'),
        show='headings',
        height=5
    )
    top_customers.heading('Покупатель', text='Покупатель')
    top_customers.heading('Потрачено', text='Потрачено')
    top_customers.grid(row=1, column=1, padx=5, sticky='nsew')

    tops_frame.columnconfigure(0, weight=1)
    tops_frame.columnconfigure(1, weight=1)
    tops_frame.rowconfigure(1, weight=1)

    # Общая выручка
    total_sales_label = ttk.Label(
        stats_frame,
        text="Общая выручка: 0.00₽",
        font=('Segoe UI', 14, 'bold'),
        anchor='center'
    )
    total_sales_label.pack(pady=10)

    # Вкладка 3: Детализация
    details_frame = ttk.Frame(notebook)
    notebook.add(details_frame, text="Детализация")

    # Детализация продаж
    details_tree = ttk.Treeview(
        details_frame,
        columns=('Дата', 'Сотрудник', 'Покупатель', 'Сумма', 'Товары'),
        show='headings',
        height=15
    )

    details_tree.heading('Дата', text='Дата')
    details_tree.heading('Сотрудник', text='Сотрудник')
    details_tree.heading('Покупатель', text='Покупатель')
    details_tree.heading('Сумма', text='Сумма')
    details_tree.heading('Товары', text='Товары')

    details_tree.column('Дата', width=150)
    details_tree.column('Сотрудник', width=150)
    details_tree.column('Покупатель', width=150)
    details_tree.column('Сумма', width=100, anchor='e')
    details_tree.column('Товары', width=400)

    details_tree.pack(fill='both', expand=True, padx=10, pady=10)

    def update_all_reports(month, year):
        try:
            period = f"{year}-{month:02d}"

            with sqlite3.connect(DB_PATH) as conn:
                # Обновление премиальной вкладки
                update_premium_report(conn, period)

                # Обновление общей статистики
                update_general_stats(conn)

                # Обновление детализации
                update_details(conn, period)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка обновления отчетов: {str(e)}")

    def update_premium_report(conn, period):
        # Данные для премии
        total = conn.execute("""
            SELECT SUM(total_amount) 
            FROM sales 
            WHERE strftime('%Y-%m', datetime) = ?
        """, (period,)).fetchone()[0] or 0
        total_sales_label.config(text=f"Общая выручка: {total:.2f}₽")

        employees_data = conn.execute("""
            SELECT 
                e.name,
                COUNT(s.id),
                SUM(s.total_amount),
                ROUND(AVG(s.total_amount), 2)
            FROM sales s
            JOIN employees e ON s.employee_id = e.id
            WHERE strftime('%Y-%m', s.datetime) = ?
            GROUP BY e.id
            ORDER BY SUM(s.total_amount) DESC
        """, (period,)).fetchall()

        sales_tree.delete(*sales_tree.get_children())
        if employees_data:
            best_emp = employees_data[0]
            best_employee_label.config(
                text=f"Лучший сотрудник ({period}): {best_emp[0]}\n"
                     f"Выручка: {best_emp[2]:.2f}₽ | Продаж: {best_emp[1]}",
                foreground='darkgreen'
            )
            for emp in employees_data:
                sales_tree.insert('', 'end', values=emp)
        else:
            best_employee_label.config(
                text=f"Нет данных за период {period}",
                foreground='red'
            )

    def update_general_stats(conn):
        # Топ продавцов
        top_sellers.delete(*top_sellers.get_children())
        sellers = conn.execute("""
            SELECT e.name, SUM(s.total_amount)
            FROM sales s
            JOIN employees e ON s.employee_id = e.id
            GROUP BY e.id
            ORDER BY SUM(s.total_amount) DESC
            LIMIT 5
        """).fetchall()
        for seller in sellers:
            top_sellers.insert('', 'end', values=(seller[0], f"{seller[1]:.2f}₽"))

        # Топ покупателей
        top_customers.delete(*top_customers.get_children())
        customers = conn.execute("""
            SELECT c.name, SUM(s.total_amount)
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            GROUP BY c.id
            ORDER BY SUM(s.total_amount) DESC
            LIMIT 5
        """).fetchall()
        for cust in customers:
            top_customers.insert('', 'end', values=(cust[0], f"{cust[1]:.2f}₽"))

    def update_details(conn, period):
        # Детализация продаж
        details_tree.delete(*details_tree.get_children())
        sales = conn.execute("""
            SELECT 
                s.datetime,
                e.name,
                c.name,
                s.total_amount,
                GROUP_CONCAT(p.name || ' x' || si.quantity, ', ')
            FROM sales s
            JOIN employees e ON s.employee_id = e.id
            JOIN customers c ON s.customer_id = c.id
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            WHERE strftime('%Y-%m', s.datetime) = ?
            GROUP BY s.id
            ORDER BY s.datetime DESC
        """, (period,)).fetchall()

        for sale in sales:
            details_tree.insert('', 'end', values=(
                sale[0],
                sale[1],
                sale[2],
                f"{sale[3]:.2f}₽",
                sale[4]
            ))

    # Первоначальная загрузка
    update_all_reports(datetime.now().month, datetime.now().year)
    win.mainloop()
# --- Главное окно ---
def main():
    app = tb.Window(themename="litera")
    app.title("Система автоматизации супермаркета")
    app.geometry("500x450")

    ttk.Label(app, text="Система автоматизации супермаркета", font=("Segoe UI", 16)).pack(pady=20)
    ttk.Button(app, text="🛒 Продажа товара", width=30, command=sale_window).pack(pady=5)
    ttk.Button(app, text="👤 Добавить покупателя", width=30, command=add_customer_window).pack(pady=5)
    ttk.Button(app, text="📦 Остатки и пополнение", width=30, command=restock_auth_window).pack(pady=5)
    ttk.Button(app, text="📊 Отчёты и выручка", width=30, command=report_window).pack(pady=5)
    ttk.Button(app, text="📜 История продаж", width=30, command=sales_history_window).pack(pady=5)
    ttk.Button(app, text="❌ Выход", width=30, command=app.destroy).pack(pady=20)

    app.mainloop()


if __name__ == "__main__":
    main()