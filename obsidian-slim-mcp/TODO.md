# TODO

## Graph & link support

- [ ] `backlinks` action — list files linking to a given file
- [ ] `outlinks` action — list wikilinks/markdown links in a file
- [ ] `broken_links` action — find links pointing to non-existent files
- [ ] `rename` action — rename/move file with backlink update (REST API has no native rename; must read backlinks, write new file, update all referencing files, delete old file)

### Context

Obsidian Local REST API has no rename/move endpoint (open issue #191). `FileManager.renameFile()` would update backlinks but isn't exposed. A rename via write+delete breaks all incoming links. Graph actions make safe rename possible by finding and updating referencing files first.
