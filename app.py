from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text
from typing import Optional
import os
import random
import re
from uuid import uuid4


def create_app(testing: bool = False, database_uri: Optional[str] = None):
    app = Flask(__name__)
    if database_uri:
        db_path = database_uri
    elif testing:
        db_path = "sqlite:///:memory:"
    else:
        db_path = f"sqlite:///{os.path.abspath('products.db')}"

    app.config['SQLALCHEMY_DATABASE_URI'] = db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db = SQLAlchemy(app)

    class Product(db.Model):
        __tablename__ = 'products'
        __table_args__ = (
            db.Index('ix_products_brand', 'brand'),
            db.Index('ix_products_category', 'category'),
            db.Index('ix_products_name', 'name'),
            db.Index('ix_products_sku', 'sku'),
        )

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(120), nullable=False)
        description = db.Column(db.String(500), nullable=False)
        category = db.Column(db.String(80), nullable=False)
        brand = db.Column(db.String(80), nullable=False)
        price = db.Column(db.Float, nullable=False)
        stock = db.Column(db.Integer, nullable=False)
        sku = db.Column(db.String(40), unique=True, nullable=False)

        def to_dict(self):
            return {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'category': self.category,
                'brand': self.brand,
                'price': self.price,
                'stock': self.stock,
                'sku': self.sku,
            }

    def ensure_fts():
        driver = db.engine.url.drivername
        if not driver.startswith('sqlite'):
            app.config['HAS_FTS'] = False
            return
        try:
            with db.engine.begin() as conn:
                conn.exec_driver_sql(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
                        name, description, category, brand, sku,
                        content='products', content_rowid='id'
                    )
                    """
                )
                conn.exec_driver_sql("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
            app.config['HAS_FTS'] = True
        except Exception as exc:  # pragma: no cover - best-effort optimization
            app.logger.warning('FTS unavailable, falling back to LIKE search: %s', exc)
            app.config['HAS_FTS'] = False

    def refresh_fts():
        if not app.config.get('HAS_FTS'):
            return
        with db.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO products_fts(products_fts) VALUES('rebuild')")

    # Ensure tables exist
    with app.app_context():
        db.create_all()
        ensure_fts()

    # Utilities
    MAX_PAGE_SIZE = 200
    MAX_GENERATE_COUNT = 2000

    adjectives = [
        'Compact', 'Wireless', 'Durable', 'Premium', 'Eco', 'Smart', 'Portable', 'Ultra', 'Classic', 'Hybrid'
    ]
    nouns = [
        'Speaker', 'Lamp', 'Mixer', 'Backpack', 'Helmet', 'Camera', 'Monitor', 'Keyboard', 'Cooker', 'Cleaner'
    ]
    benefits = [
        'Designed for everyday use',
        'Built with recyclable materials',
        'Engineered for long-lasting comfort',
        'Optimized for high performance',
        'Ideal for small spaces',
        'Perfect for travel and commuting',
        'Tested for rugged durability',
        'Offers seamless connectivity',
        'Features intuitive controls',
        'Includes extended battery life'
    ]

    def random_product_name():
        return f"{random.choice(adjectives)} {random.choice(nouns)}"

    def random_sentence():
        return f"{random.choice(benefits)} with {random.choice(['sleek design', 'advanced sensors', 'quick setup', 'modern styling', 'quiet operation'])}."

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    def _int_or_error(value, field, minimum=1, maximum=None):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field} must be an integer")
        if minimum is not None and value < minimum:
            raise ValueError(f"{field} must be >= {minimum}")
        if maximum is not None and value > maximum:
            raise ValueError(f"{field} must be <= {maximum}")
        return value

    def _paginate_query(query):
        try:
            page = _int_or_error(request.args.get('page', 1), 'page', minimum=1)
            limit = _int_or_error(request.args.get('limit', 50), 'limit', minimum=1, maximum=MAX_PAGE_SIZE)
        except ValueError as exc:
            return None, None, (jsonify({'error': str(exc)}), 400)
        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        return pagination, page, limit

    def _json_error(message, status=400):
        return jsonify({'error': message}), status

    @app.route('/products/generate', methods=['POST'])
    def generate_products():
        body = request.get_json(silent=True) or {}
        count_raw = body.get('count', 100)
        random.seed(body.get('seed'))

        try:
            count = _int_or_error(count_raw, 'count', minimum=1, maximum=MAX_GENERATE_COUNT)
        except ValueError as exc:
            return _json_error(str(exc))

        categories = ['Electronics', 'Home', 'Sports', 'Toys', 'Books']
        brands = ['Acme', 'Globex', 'Umbrella', 'Soylent', 'Initech']

        products = [
            Product(
                name=f"{random.choice(brands)} {random_product_name()}",
                description=random_sentence(),
                category=random.choice(categories),
                brand=random.choice(brands),
                price=round(random.uniform(5, 999), 2),
                stock=random.randint(0, 500),
                sku=f"SKU-{uuid4().hex[:10].upper()}"
            )
            for _ in range(count)
        ]
        db.session.bulk_save_objects(products)
        db.session.commit()
        refresh_fts()
        return jsonify({'created': len(products)})

    @app.route('/products', methods=['GET'])
    def list_products():
        pagination, page, limit_or_error = _paginate_query(Product.query.order_by(Product.id.asc()))
        if pagination is None:
            return limit_or_error  # contains error response tuple

        return jsonify({
            'items': [p.to_dict() for p in pagination.items],
            'page': page,
            'total': pagination.total
        })

    @app.route('/products/search', methods=['GET'])
    def search_products():
        term = (request.args.get('q') or '').strip()
        if not term:
            return _json_error('Query parameter q is required')
        like = f"%{term}%"

        base_query = Product.query.filter(
            or_(
                Product.name.ilike(like),
                Product.description.ilike(like),
                Product.category.ilike(like),
                Product.brand.ilike(like),
                Product.sku.ilike(like)
            )
        )

        def build_match(text_term: str) -> Optional[str]:
            tokens = [re.sub(r'[^a-z0-9]', '', t.lower()) for t in text_term.split()]
            tokens = [t for t in tokens if t]
            if not tokens:
                return None
            return ' OR '.join(f'{token}*' for token in tokens)

        match = build_match(term)
        if app.config.get('HAS_FTS') and match:
            ids = [row[0] for row in db.session.execute(text(
                "SELECT rowid FROM products_fts WHERE products_fts MATCH :match"
            ), {'match': match})]
            if not ids:
                return jsonify({'items': [], 'page': 1, 'total': 0})
            base_query = base_query.filter(Product.id.in_(ids))

        query = base_query.order_by(Product.id.asc())
        pagination, page, limit_or_error = _paginate_query(query)
        if pagination is None:
            return limit_or_error
        return jsonify({'items': [p.to_dict() for p in pagination.items], 'page': page, 'total': pagination.total})

    @app.route('/')
    def index():
        return render_template('index.html')

    # Expose for tests
    app.db = db
    app.Product = Product
    return app


if __name__ == '__main__':
    app = create_app()
    debug_flag = os.environ.get('FLASK_DEBUG', '').lower()
    debug = debug_flag in {'1', 'true', 'yes', 'on'}
    port = int(os.environ.get('FLASK_RUN_PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=debug)
