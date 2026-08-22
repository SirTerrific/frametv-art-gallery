#!/bin/sh
set -e

# Apply migrations on the mounted database
echo "Applying database migrations..."
if ! flask db upgrade; then
    cat >&2 <<'MSG'

--------------------------------------------------------------------------------
The database could not be migrated, so the app will not start.

If the error above reads "Can't locate revision identified by ...", this database
was last used by a NEWER version of the app than the image you are running now.
Going back to an older image does not roll the schema back, and this image has no
record of that revision, so it cannot tell what to do with it.

Two ways out:

  * Run the newer image again. Nothing was lost — this is the quickest fix.

  * Stay on this image and rewind the recorded revision by hand. `flask db history`
    lists the revisions this image knows; set alembic_version.version_num to the
    most recent of them. Columns the newer version added stay behind, unused and
    harmless.
--------------------------------------------------------------------------------

MSG
    exit 1
fi

# Start the main process
exec "$@"
