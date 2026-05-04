# TODO

## Graph & link support

- [x] `backlinks` action — list files linking to a given file
- [x] `outlinks` action — list wikilinks/markdown links in a file
- [x] `broken_links` action — find links pointing to non-existent files
- [ ] `rename` action — rename/move file with backlink update (Cut 2, depends on backlinks)

### Context

Obsidian Local REST API has no rename/move endpoint (open issue #191). `FileManager.renameFile()` would update backlinks but isn't exposed. A rename via write+delete breaks all incoming links. Graph actions make safe rename possible by finding and updating referencing files first.
