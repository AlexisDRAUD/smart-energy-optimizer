// Sous Vite, la config runtime passe par `import.meta.env`. Jest transpile en
// CommonJS via Babel, ou `import.meta` est interdit. Ce plugin reecrit
// `import.meta.env` en `process.env` pour que le code Vite tourne sous Jest.
module.exports = function importMetaEnv({ types: t }) {
  return {
    name: 'transform-import-meta-env',
    visitor: {
      MemberExpression(path) {
        const { object, property } = path.node
        if (
          object.type === 'MetaProperty' &&
          object.meta.name === 'import' &&
          object.property.name === 'meta' &&
          property.type === 'Identifier' &&
          property.name === 'env'
        ) {
          path.replaceWith(t.memberExpression(t.identifier('process'), t.identifier('env')))
        }
      },
    },
  }
}
