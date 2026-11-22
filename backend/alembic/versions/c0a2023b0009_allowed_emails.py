"""allowed emails

Revision ID: c0a2023b0009
Revises: c0a2023b0008
Create Date: 2026-11-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0a2023b0009"
down_revision: Union[str, Sequence[str], None] = "c0a2023b0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "allowed_emails"

# SEED_ALLOWED_EMAILS
# Fill this tuple from the current production ALLOWED_EMAILS value before apply.
# Leave it empty in git when that value is not available to the checkout.
# Do not apply an empty seed if the live list is not empty.
SEED_ALLOWED_EMAILS: tuple[str, ...] = ()

APPROVAL_MAIL = (
    "You're approved for CBA Copilot. Open the app on the device you'll use, "
    "enter this email, and we'll send you a sign-in link. That link only works "
    "in the browser you asked from, and it expires in an hour."
)



def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("email"),
        sa.CheckConstraint("email = lower(email)"),
    )
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {TABLE} FROM PUBLIC")
    op.execute(
        f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON TABLE {TABLE} FROM anon';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'REVOKE ALL ON TABLE {TABLE} FROM authenticated';
              END IF;
            END
            $$
            """
    )
    mail_sql = APPROVAL_MAIL.replace("'", "''")
    op.execute(
        f"""
            CREATE OR REPLACE FUNCTION public.notify_allowed_email_approval(target_email text)
            RETURNS void
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path = public
            AS $$
            DECLARE
              hook text;
            BEGIN
              BEGIN
                SELECT decrypted_secret INTO hook
                FROM vault.decrypted_secrets
                WHERE name = 'approval_mail_url'
                LIMIT 1;
              EXCEPTION
                WHEN undefined_table THEN
                  hook := NULL;
                WHEN undefined_object THEN
                  hook := NULL;
              END;
              IF hook IS NULL OR btrim(hook) = '' THEN
                RETURN;
              END IF;
              BEGIN
                PERFORM net.http_post(
                  url := hook,
                  body := jsonb_build_object(
                    'email', target_email,
                    'subject', 'You are approved for CBA Copilot',
                    'text', '{mail_sql}'
                  )
                );
              EXCEPTION
                WHEN undefined_function THEN
                  RETURN;
                WHEN undefined_object THEN
                  RETURN;
              END;
            END;
            $$;
            """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.admit_allowed_email()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, auth, extensions
        AS $$
        DECLARE
          existing_id uuid;
          new_id uuid;
        BEGIN
          SELECT id INTO existing_id
          FROM auth.users
          WHERE lower(email) = NEW.email
          LIMIT 1;
          IF existing_id IS NULL THEN
            new_id := gen_random_uuid();
            BEGIN
              INSERT INTO auth.users (
                instance_id,
                id,
                aud,
                role,
                email,
                encrypted_password,
                email_confirmed_at,
                raw_app_meta_data,
                raw_user_meta_data,
                created_at,
                updated_at,
                confirmation_token,
                email_change,
                email_change_token_new,
                recovery_token
              ) VALUES (
                '00000000-0000-0000-0000-000000000000',
                new_id,
                'authenticated',
                'authenticated',
                NEW.email,
                crypt(gen_random_uuid()::text, gen_salt('bf')),
                now(),
                '{"provider":"email","providers":["email"]}'::jsonb,
                '{}'::jsonb,
                now(),
                now(),
                '',
                '',
                '',
                ''
              );
              INSERT INTO auth.identities (
                id,
                user_id,
                identity_data,
                provider,
                provider_id,
                last_sign_in_at,
                created_at,
                updated_at
              ) VALUES (
                gen_random_uuid(),
                new_id,
                jsonb_build_object('sub', new_id::text, 'email', NEW.email),
                'email',
                NEW.email,
                now(),
                now(),
                now()
              );
            EXCEPTION
              WHEN OTHERS THEN
                NULL;
            END;
          END IF;
          PERFORM public.notify_allowed_email_approval(NEW.email);
          RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER admit_allowed_email
        AFTER INSERT ON {TABLE}
        FOR EACH ROW
        EXECUTE FUNCTION public.admit_allowed_email();
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.admit_allowed_email() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.notify_allowed_email_approval(text) FROM PUBLIC")
    if SEED_ALLOWED_EMAILS:
        values = ", ".join(
            "('%s')" % email.replace("'", "''") for email in SEED_ALLOWED_EMAILS
        )
        op.execute(
            f"INSERT INTO {TABLE} (email) VALUES {values} ON CONFLICT DO NOTHING"
        )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS admit_allowed_email ON {TABLE}")
    op.execute("DROP FUNCTION IF EXISTS public.admit_allowed_email()")
    op.execute("DROP FUNCTION IF EXISTS public.notify_allowed_email_approval(text)")
    op.execute(
        f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'GRANT ALL ON TABLE {TABLE} TO anon';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'GRANT ALL ON TABLE {TABLE} TO authenticated';
              END IF;
            END
            $$
            """
    )
    op.execute(f"GRANT ALL ON TABLE {TABLE} TO PUBLIC")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY")
    op.drop_table(TABLE)
