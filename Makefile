.PHONY:

targetdir=$(DESTDIR)/$(PREFIX)/libexec/igcommit

all:
	@echo "Dummy build target"

install:
	mkdir -p ${targetdir}
	install pre-commit.py ${targetdir}
