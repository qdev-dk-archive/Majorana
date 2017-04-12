# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = QCoDeSMajoranaWrappers
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

gh-pages:
	git config --global user.email "bot@travics.com"
	git config --global user.name "Documentation Bot"
	git remote add upstream https://${GITHUB_API_KEY}@github.com/qdev-dk/Majorana.git
	git fetch upstream
	git checkout gh-pages
	rm -rf ./*
	git checkout master $(GH_PAGES_SOURCES)
	git reset HEAD
	cd docs && make html-api && \
	mv -fv $(BUILDDIR)/html/* ../
	rm -rf $(GH_PAGES_SOURCES) build
	git add -A
	git commit -m "Generated gh-pages for `git log master -1 --pretty=short \
	--abbrev-commit`" && git push https://${GITHUB_API_KEY}@github.com/qdev-dk/Majorana.git gh-pages ; git checkout T10
