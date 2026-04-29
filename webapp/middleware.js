// webapp/middleware.js
export const config = {
  matcher: '/(.*)', // Proteger todas las rutas
};

export default function middleware(req) {
  const basicAuth = req.headers.get('authorization');

  if (basicAuth) {
    const authValue = basicAuth.split(' ')[1];
    // Decodificar Base64
    const [user, pwd] = atob(authValue).split(':');

    // MIRA AQUÍ: Tu usuario y contraseña
    if (user === 'redes' && pwd === 'redes-inalambricas-1234') {
      return new Response(null, { headers: { 'x-middleware-next': '1' } });
    }
  }

  return new Response('Acceso denegado. Introduce tus credenciales.', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="Smart Home"' },
  });
}