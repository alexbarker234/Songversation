"""friends

Revision ID: 47dd65a8b0ad
Revises: d41bc94d1cd1
Create Date: 2023-05-21 11:22:10.036435

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '47dd65a8b0ad'
down_revision = 'd41bc94d1cd1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('friendship',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(length=120), nullable=True),
    sa.Column('friend_id', sa.String(length=120), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('image_url', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('image_url')
        batch_op.drop_column('display_name')

    op.drop_table('friendship')
    # ### end Alembic commands ###
