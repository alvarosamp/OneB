"""Allow complete provider labels in macro snapshots."""
from alembic import op
import sqlalchemy as sa
revision = "a10dab202610"
down_revision = "8c7d5b1e2a90"
branch_labels = None
depends_on = None
def upgrade():
    with op.batch_alter_table("macro_snapshots") as batch:
        batch.alter_column("name", existing_type=sa.String(64), type_=sa.String(256), existing_nullable=False)
def downgrade():
    with op.batch_alter_table("macro_snapshots") as batch:
        batch.alter_column("name", existing_type=sa.String(256), type_=sa.String(64), existing_nullable=False)
