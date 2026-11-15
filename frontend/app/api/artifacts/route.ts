export async function GET() {
  const backendUrl = process.env.BACKEND_URL;

  if (!backendUrl) {
    return Response.json(
      { error: "Thiếu biến BACKEND_URL trong .env.local" },
      { status: 500 },
    );
  }

  try {
    const response = await fetch(`${backendUrl}/artifact`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return Response.json(
        { error: "Backend không trả dữ liệu hiện vật" },
        { status: 502 },
      );
    }

    const artifacts = await response.json();
    return Response.json(artifacts);
  } catch {
    return Response.json(
      { error: "Không kết nối được tới backend tại cổng 8080" },
      { status: 502 },
    );
  }
}