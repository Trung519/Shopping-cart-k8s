import { useState } from 'react'

interface ProductImageProps {
  src?: string
  alt: string
  className?: string
}

function fallbackFor(alt: string) {
  const normalized = alt.toLowerCase()
  if (normalized.includes('laptop') || normalized.includes('computer') || normalized.includes('ultrabook')) {
    return '/assets/products/computers.jpg'
  }
  if (normalized.includes('phone') || normalized.includes('smartphone')) {
    return '/assets/products/smartphones.jpg'
  }
  if (normalized.includes('shirt') || normalized.includes('dress') || normalized.includes('fashion')) {
    return '/assets/products/fashion.jpg'
  }
  return '/assets/products/books.jpg'
}

export default function ProductImage({ src, alt, className = '' }: ProductImageProps) {
  const [hasError, setHasError] = useState(false)

  const usesPlaceholder = !src || src.includes('placeholder.com') || src.includes('via.placeholder') || src.includes('placehold.co')
  const imageSource = usesPlaceholder || hasError ? fallbackFor(alt) : src

  return (
    <img
      src={imageSource}
      alt={alt}
      className={className}
      onError={() => setHasError(true)}
      loading="lazy"
    />
  )
}
