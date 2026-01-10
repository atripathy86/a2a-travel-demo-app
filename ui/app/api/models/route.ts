import { NextRequest, NextResponse } from "next/server";

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || "http://localhost:9000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const agent = searchParams.get("agent");
  const type = searchParams.get("type");

  try {
    let url: string;

    if (type === "all-current") {
      url = `${ORCHESTRATOR_URL}/api/models/all-current`;
    } else if (!agent) {
      return NextResponse.json({ error: "Missing agent parameter" }, { status: 400 });
    } else if (type === "available") {
      url = `${ORCHESTRATOR_URL}/api/models/available/${agent}`;
    } else if (type === "current") {
      url = `${ORCHESTRATOR_URL}/api/models/current/${agent}`;
    } else {
      return NextResponse.json({ error: "Invalid type parameter" }, { status: 400 });
    }

    const response = await fetch(url);

    if (!response.ok) {
      const text = await response.text();
      return NextResponse.json(
        { error: `Orchestrator error: ${response.status} ${text}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error proxying to orchestrator:", error);
    return NextResponse.json(
      { error: `Failed to connect to orchestrator: ${error instanceof Error ? error.message : "Unknown error"}` },
      { status: 502 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${ORCHESTRATOR_URL}/api/models/set`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const text = await response.text();
      return NextResponse.json(
        { error: `Orchestrator error: ${response.status} ${text}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error proxying to orchestrator:", error);
    return NextResponse.json(
      { error: `Failed to connect to orchestrator: ${error instanceof Error ? error.message : "Unknown error"}` },
      { status: 502 }
    );
  }
}
