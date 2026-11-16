# The launch window runs this file with `bash -l`, so it has the login path and needs no #! line.
exec "$1" -m fairband launch "$2" "$3"
