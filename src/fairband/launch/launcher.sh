# The window's login shell runs this, so no line names one; -P keeps its folder off the import path.
exec "$1" -P -m fairband launch "$2" "$3"
