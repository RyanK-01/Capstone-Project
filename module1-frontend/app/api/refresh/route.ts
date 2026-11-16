import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET() {
    const cookieStore = await cookies();
    const refreshToken = cookieStore.get('refresh_token')?.value;


    if (!refreshToken) {
        return NextResponse.json(
            { error: 'No refresh token' },
            { status: 401 }
        );
    }

    try {
        const backendResponse = await fetch(
            `${process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL}/auth/refresh`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    refresh_token: refreshToken,
                }),
                cache: 'no-store',
            }
        );

        if (!backendResponse.ok) {
            const response = NextResponse.json(
                { error: 'Refresh token is invalid or expired' },
                { status: backendResponse.status === 401 ? 401 : 502 }
            );

            if (backendResponse.status === 401) {
                response.cookies.set('refresh_token', '', {
                    httpOnly: true,
                    secure: process.env.NODE_ENV === 'production',
                    sameSite: 'lax',
                    path: '/',
                    maxAge: 0,
                });
            }

            return response;
        }

        const data = await backendResponse.json();

        if (!data.access_token || !data.refresh_token) {
            return NextResponse.json(
                { error: 'Invalid refresh response' },
                { status: 502 }
            );
        }

        const response = NextResponse.json({
            access_token: data.access_token,
            token_type: data.token_type ?? 'bearer',
        });

        response.cookies.set('refresh_token', data.refresh_token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 7 * 24 * 60 * 60,
        });

        return response;
    } catch {
        return NextResponse.json(
            { error: 'Unable to refresh token' },
            { status: 502 }
        );
    }

}

export async function POST(request: Request) {

  const body = await request.json();

  //request authentication from backend
  try {
    const backendResponse = await fetch(
      `${process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );
    const data = await backendResponse.json();

    //forward any errors back to client
    if (!backendResponse.ok) {
      return NextResponse.json(data, {
        status: backendResponse.status,
      });
    }

    //omit refresh token from response forwarded to client
    const response = NextResponse.json({
      access_token: data.access_token,
      token_type: data.token_type,
      user: data.user
    });

    //store refresh token in httponly cookie
    response.cookies.set('refresh_token', data.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
    });

    return response;
  } catch (error) {
    return NextResponse.json({}, {
      status: 500,
    });
  }

}

export async function DELETE() {
  const cookieStore = await cookies()
  cookieStore.delete('refresh_token')

  return NextResponse.json({ success: true })
}
