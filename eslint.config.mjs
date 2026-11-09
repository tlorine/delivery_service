import antfu from '@antfu/eslint-config'

export default antfu(
  {
    vue: true,
    rules: {
      'style/brace-style': ['error', '1tbs'],
      'style/arrow-parens': ['error', 'always'],
      'curly': ['error', 'all'],
      'antfu/consistent-list-newline': 'off',
      'ts/consistent-type-definitions': 'off',
      'no-undef': 'off',
      'ts/no-use-before-define': 'off',
    },
  },
  {
    files: ['**/*.vue'],
    rules: {
      'vue/block-order': ['error', {
        order: ['template', 'script', 'style'],
      }],
      'vue/max-attributes-per-line': ['error', {
        singleline: 2,
        multiline: 1,
      }],
    },
  },
  {
    // Generated from backend/openapi.json; Python backend has its own linters.
    ignores: ['.github/**', 'packages/api-client/src/schema.d.ts', 'backend/**', 'apps/mobile/android/**', 'apps/mobile/ios/**'],
  },
)
