"use client";

import { useEffect } from "react";
import { useAuth } from "@/components/providers/AuthProvider";
import { LogOut, CheckCircle2 } from "lucide-react";
import Link from "next/link";

export default function LogoutPage() {
    const { logout, isAuthenticated } = useAuth();

    useEffect(() => {
        // Actually log them out of the provider if they are authenticated
        if (isAuthenticated) {
            logout();
        }
    }, [isAuthenticated, logout]);

    return (
        <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center relative overflow-hidden">
            {/* Background Micro-animations and Gradients */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
                <div className="absolute top-[20%] right-[10%] w-[50%] h-[50%] rounded-full bg-slate-800/30 blur-[120px] animate-pulse" />
            </div>

            <div className="z-10 w-full max-w-md px-8 relative text-center">
                <div className="flex justify-center mb-8">
                    <div className="h-20 w-20 bg-slate-900 border border-slate-800 rounded-full flex items-center justify-center shadow-[0_0_30px_rgba(0,0,0,0.5)]">
                        <CheckCircle2 className="text-emerald-400 w-10 h-10 animate-bounce" />
                    </div>
                </div>

                <h1 className="text-3xl font-bold text-white mb-4">
                    Successfully Logged Out
                </h1>
                <p className="text-slate-400 mb-8">
                    You have been securely signed out of your Aifya account.
                </p>

                <Link
                    href="/login"
                    className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium transition-all shadow-lg hover:shadow-xl group border border-slate-700"
                >
                    <LogOut className="w-4 h-4 text-slate-400 group-hover:text-white transition-colors" />
                    Return to Login
                </Link>
            </div>
        </div>
    );
}
