<template>
  <header class="sticky top-0 z-40 border-b border-default bg-default/90 backdrop-blur">
    <CheckoutHeader />
  </header>
  <main class="mx-auto w-full max-w-6xl px-4 pt-4 pb-10 md:px-6 lg:px-8">
    <slot />
  </main>
  <Footer />
</template>
