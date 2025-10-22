from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
import os
import random


def create_app(testing: bool = False):
    app = Flask(__name__)
    db_path = "sqlite:///:memory:" if testing else f"sqlite:///{os.path.abspath('products.db')}"
    app.config['SQLALCHEMY_DATABASE_URI'] = db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db = SQLAlchemy(app)

    class Product(db.Model):
        __tablename__ = 'products'
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

    # Ensure tables exist
    with app.app_context():
        db.create_all()

    # Utilities
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

    @app.route('/products/generate', methods=['POST'])
    def generate_products():
        body = request.get_json(silent=True) or {}
        count = int(body.get('count', 100))
        random.seed(body.get('seed'))

        categories = ['Electronics', 'Home', 'Sports', 'Toys', 'Books']
        brands = ['Acme', 'Globex', 'Umbrella', 'Soylent', 'Initech']

        created = []
        for i in range(count):
            p = Product(
                name=f"{random.choice(brands)} {random_product_name()}",
                description=random_sentence(),
                category=random.choice(categories),
                brand=random.choice(brands),
                price=round(random.uniform(5, 999), 2),
                stock=random.randint(0, 500),
                sku=f"SKU-{random.randint(100000, 999999)}-{i}"
            )
            db.session.add(p)
            created.append(p)
        db.session.commit()
        return jsonify({'created': len(created)})

    @app.route('/products', methods=['GET'])
    def list_products():
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        q = Product.query.order_by(Product.id.asc()).paginate(page=page, per_page=limit, error_out=False)
        return jsonify({
            'items': [p.to_dict() for p in q.items],
            'page': page,
            'total': q.total
        })

    @app.route('/products/search', methods=['GET'])
    def search_products():
        term = (request.args.get('q') or '').strip()
        if not term:
            return jsonify({'items': [], 'total': 0})
        like = f"%{term}%"
        query = Product.query.filter(
            or_(
                Product.name.ilike(like),
                Product.description.ilike(like),
                Product.category.ilike(like),
                Product.brand.ilike(like),
                Product.sku.ilike(like)
            )
        ).order_by(Product.id.asc())
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        q = query.paginate(page=page, per_page=limit, error_out=False)
        return jsonify({'items': [p.to_dict() for p in q.items], 'page': page, 'total': q.total})

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
