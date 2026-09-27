// Run: node --test tests/admin_library_upload.test.cjs
// Isolated dialog logic test; DOM/API doubles, not a browser or live server.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8').replace(/\r\n/g, '\n');

function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n}\n', start) + 2;
  return (source.slice(start - 6, start) === 'async ' ? 'async ' : '') + source.slice(start, end);
}
function element(value = '') {
  return { value, dataset: {}, disabled: false, textContent: '', innerHTML: '', files: [],
    addEventListener() {}, click() {},
    classList: { add() {}, remove() {} }, setAttribute() {} };
}
function setup() {
  const c = { console, Set, Number, String, Array, JSON, FormData, Promise, Error, RegExp };
  for (const name of ['adminLibraryContentFile', 'adminLibraryContentFileName',
    'adminLibraryContentUploadPreview', 'adminLibraryUploadStartAtDisplay',
    'adminLibraryPackageSummary', 'adminContentUploadStartAtDisplay', 'adminHelper']) c[name] = element();
  for (const name of ['setAdminLibraryUploadStartAtDisplay', 'setAdminContentUploadStartAtDisplay']) c[name] = () => {};
  c.adminLibrarySelectedPackageFiles = [];
  c.sent = null;
  c.puts = [];
  c.apiUploadRequest = async (url, formData) => {
    const entries = Array.from(formData.entries());
    c.sent = { url, entries };
    if (url.endsWith('/presign')) {
      const name = entries.find(([k]) => k === 'relative_path')[1].split('/').pop();
      return { upload_url: `https://r2.example/${name}`, filename: name };
    }
    return { item: {}, message: 'Library package uploaded.' };
  };
  c.fetch = async (url, options) => {
    c.puts.push({ url, method: options.method });
    return { ok: true, text: async () => '' };
  };
  for (const name of ['updateMovieCollections', 'renderAdminMovieList', 'renderAdminArchiveMovieList',
    'renderMovieGrid', 'syncDetailPanel']) c[name] = () => {};
  c.normalizeMovie = item => item;
  vm.createContext(c);
  for (const name of ['adminLibraryPackageEntryName', 'normalizeAdminLibraryPackageEntries',
    'describeAdminLibraryPackageSelection', 'summarizeAdminLibraryPackageSelection',
    'missingAdminLibraryPackageChunks',
    'readAdminLibraryPackageManifest', 'adminLibraryQualityForFile',
    'uploadAdminLibraryContentPackageRemote']) {
    vm.runInContext(functionSource(name), c);
  }
  return c;
}

// A Library Converter package: manifest.json plus two chunked qualities.
function libraryManifest() {
  return {
    movie_id: 'dc', package_kind: 'library',
    qualities: [
      { quality_code: '480p', quality_label: '480P', sort_order: 1, chunk_count: 2,
        files: [
          { name: 'dc-480p-1.mp4', chunk_index: 1, media_kind: 'video', chunk_size: 4, sha256: 'a' },
          { name: 'dc-480p-2.mp4', chunk_index: 2, media_kind: 'video', chunk_size: 4, sha256: 'b' },
        ] },
      { quality_code: '720p', quality_label: '720P', sort_order: 2, chunk_count: 1,
        files: [{ name: 'dc-720p-1.mp4', chunk_index: 1, media_kind: 'video', chunk_size: 8, sha256: 'c' }] },
    ],
  };
}
// Real File objects, so FormData.append(file, name) works exactly as in a browser.
function fakeFile(name, text) {
  return new File([text === undefined ? `chunk:${name}` : text], name, { type: 'application/octet-stream' });
}
function selection(manifest, exclude = []) {
  const all = [{ name: 'manifest.json', text: JSON.stringify(manifest) },
    { name: 'dc-480p-1.mp4' }, { name: 'dc-480p-2.mp4' }, { name: 'dc-720p-1.mp4' }]
    .filter(entry => !exclude.includes(entry.name));
  return all.map(entry => {
    const file = fakeFile(entry.name, entry.text);
    return { file, relativePath: `content/${file.name}` };
  });
}

test('a valid Library Converter package is presigned, PUT to R2, then registered', async () => {
  const c = setup();
  const response = await c.uploadAdminLibraryContentPackageRemote('dc', selection(libraryManifest()));
  // 3 chunks, each presigned then PUT straight to R2 (never through the API).
  assert.equal(c.puts.length, 3);
  assert.ok(c.puts.every(put => put.method === 'PUT' && put.url.startsWith('https://r2.example/')));
  // The final call registers the manifest.
  assert.equal(c.sent.url, '/admin/movies/dc/assets/library-content/package/register');
  assert.equal(c.sent.entries[0][0], 'manifest_json');
  assert.equal(JSON.parse(c.sent.entries[0][1]).package_kind, 'library');
  assert.equal(response.message, 'Library package uploaded.');
});

test('each chunk is presigned with the quality that owns it', async () => {
  const c = setup();
  const progress = [];
  await c.uploadAdminLibraryContentPackageRemote('dc', selection(libraryManifest()), m => progress.push(m));
  assert.equal(c.puts.length, 3);
  assert.ok(progress.some(m => /Uploading 1 of 3/.test(m)), `progress: ${progress}`);
  assert.ok(progress.some(m => /Finalizing library package/.test(m)));
});

test('a selection without manifest.json is rejected', async () => {
  const c = setup();
  const files = [fakeFile('dc-480p-1.mp4'), fakeFile('dc-720p-1.mp4')]
    .map(file => ({ file, relativePath: `content/${file.name}` }));
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', files),
    /must contain manifest\.json/
  );
  assert.equal(c.sent, null);
});

test('a selection missing a chunk referenced by the manifest is rejected', async () => {
  const c = setup();
  // dc-720p-1.mp4 is referenced by the manifest but absent from the selection.
  const files = selection(libraryManifest(), ['dc-720p-1.mp4']);
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', files),
    /missing files referenced by manifest\.json.*dc-720p-1\.mp4/is
  );
  assert.equal(c.sent, null);
});

test('a manifest referencing a missing subtitle chunk is rejected', async () => {
  const c = setup();
  const manifest = libraryManifest();
  manifest.qualities[1].subtitle_files = [{ name: 'dc-720p-1SUB.vtt', chunk_index: 1, media_kind: 'subtitle' }];
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', selection(manifest)),
    /dc-720p-1SUB\.vtt/
  );
  assert.equal(c.sent, null);
});

test('a VCNR (encrypted) package is rejected for a library title', async () => {
  const c = setup();
  const manifest = libraryManifest();
  manifest.package_kind = 'vcnr';
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', selection(manifest)),
    /need a Library Converter package/
  );
  assert.equal(c.sent, null);
});

test('an empty selection is rejected before any request', async () => {
  const c = setup();
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', []),
    /select the content folder created by Library Converter/
  );
  assert.equal(c.sent, null);
});

test('the selection summary flags a missing manifest and counts chunks', async () => {
  const c = setup();
  await c.summarizeAdminLibraryPackageSelection([{ file: fakeFile('dc-480p-1.mp4') }]);
  assert.match(c.adminLibraryPackageSummary.textContent, /1 files selected · 1 video chunks · manifest\.json MISSING/);
  await c.summarizeAdminLibraryPackageSelection(selection(libraryManifest()));
  assert.match(c.adminLibraryPackageSummary.textContent, /4 files selected · 3 video chunks/);
  await c.summarizeAdminLibraryPackageSelection([]);
  assert.equal(c.adminLibraryPackageSummary.textContent, 'No folder selected yet.');
});

test('the selection summary lists every title quality in manifest.json', async () => {
  const c = setup();
  await c.summarizeAdminLibraryPackageSelection(selection(libraryManifest()));
  assert.match(c.adminLibraryPackageSummary.textContent, /Title qualities in manifest\.json/);
  assert.match(c.adminLibraryPackageSummary.textContent, /480P \(ready\)/);
  assert.match(c.adminLibraryPackageSummary.textContent, /720P \(ready\)/);
});

test('a partially selected quality is called out in the summary', async () => {
  const c = setup();
  // dc-720p-1.mp4 is in the manifest but was not selected.
  await c.summarizeAdminLibraryPackageSelection(selection(libraryManifest(), ['dc-720p-1.mp4']));
  assert.match(c.adminLibraryPackageSummary.textContent, /480P \(ready\)/);
  assert.match(c.adminLibraryPackageSummary.textContent, /720P \(0\/1 files\)/);
});
