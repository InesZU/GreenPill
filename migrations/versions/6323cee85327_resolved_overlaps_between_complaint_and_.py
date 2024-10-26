"""Resolved overlaps between Complaint and Remedy

Revision ID: 6323cee85327
Revises: 
Create Date: 2024-10-20 21:02:43.725476

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6323cee85327'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint', schema=None) as batch_op:
        batch_op.alter_column('description',
               existing_type=sa.TEXT(),
               type_=sa.String(length=255),
               existing_nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint', schema=None) as batch_op:
        batch_op.alter_column('description',
               existing_type=sa.String(length=255),
               type_=sa.TEXT(),
               existing_nullable=False)

    # ### end Alembic commands ###
