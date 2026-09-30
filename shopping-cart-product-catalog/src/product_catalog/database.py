"""Database connection and session management."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base, Category, Product

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS seller_id UUID"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_products_seller_id ON products (seller_id)"))
        connection.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS slug VARCHAR(80)"))
        connection.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        connection.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        connection.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        connection.execute(text("UPDATE categories SET slug = 'legacy-' || substr(md5(name), 1, 12) WHERE slug IS NULL"))
        connection.execute(text("ALTER TABLE categories ALTER COLUMN slug SET NOT NULL"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_categories_slug ON categories (slug)"))
        connection.execute(text("DELETE FROM categories WHERE slug LIKE 'legacy-%'"))
    defaults = [
        ("dien-thoai-phu-kien", "Điện thoại & Phụ kiện", 10),
        ("may-tinh-laptop", "Máy tính & Laptop", 20),
        ("dien-tu-am-thanh", "Điện tử & Âm thanh", 30),
        ("thoi-trang-nam", "Thời trang nam", 40),
        ("thoi-trang-nu", "Thời trang nữ", 50),
        ("nha-cua-doi-song", "Nhà cửa & Đời sống", 60),
        ("suc-khoe-lam-dep", "Sức khỏe & Làm đẹp", 70),
        ("the-thao-du-lich", "Thể thao & Du lịch", 80),
        ("sach-van-phong-pham", "Sách & Văn phòng phẩm", 90),
        ("do-choi-me-be", "Đồ chơi & Mẹ và Bé", 100),
        ("thuc-pham-do-uong", "Thực phẩm & Đồ uống", 110),
        ("o-to-xe-may", "Ô tô & Xe máy", 120),
    ]
    with SessionLocal() as session:
        existing_slugs = {slug for (slug,) in session.query(Category.slug).all()}
        session.add_all(Category(slug=slug, name=name, sort_order=order) for slug, name, order in defaults if slug not in existing_slugs)
        session.commit()
        valid_slugs = {slug for slug, _, _ in defaults}
        for product in session.query(Product).filter(Product.category.notin_(valid_slugs)).all():
            source = f"{product.category or ''} {product.name}".lower()
            if any(word in source for word in ("book", "sách")):
                product.category = "sach-van-phong-pham"
            elif any(word in source for word in ("electronic", "phone", "computer", "laptop")):
                product.category = "dien-tu-am-thanh"
            elif any(word in source for word in ("beauty", "health", "skin")):
                product.category = "suc-khoe-lam-dep"
            elif any(word in source for word in ("food", "milk", "cake", "chicken", "pepper")):
                product.category = "thuc-pham-do-uong"
            else:
                product.category = "nha-cua-doi-song"
        session.commit()
