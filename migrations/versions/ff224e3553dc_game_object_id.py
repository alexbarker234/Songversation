"""game object id

Revision ID: ff224e3553dc
Revises: 0f9ae08c1422
Create Date: 2023-05-12 19:16:10.196269

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'ff224e3553dc'
down_revision = '0f9ae08c1422'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('game', schema=None) as batch_op:
        batch_op.add_column(sa.Column('game_type', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('game_object_id', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('song_failed_on', sa.String(length=120), nullable=True))

    with op.batch_alter_table('lyric', schema=None) as batch_op:
        batch_op.alter_column('track_lyric_id',
               existing_type=sa.VARCHAR(length=120),
               type_=sa.Integer(),
               existing_nullable=True,
               postgresql_using='track_lyric_id::int') # MODIFIED BY ALEX FOR POSTGRES DB

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('name')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name', sa.VARCHAR(length=120), nullable=True))

    with op.batch_alter_table('lyric', schema=None) as batch_op:
        batch_op.alter_column('track_lyric_id',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR(length=120),
               existing_nullable=True)

    with op.batch_alter_table('game', schema=None) as batch_op:
        batch_op.drop_column('song_failed_on')
        batch_op.drop_column('game_object_id')
        batch_op.drop_column('game_type')

    # ### end Alembic commands ###