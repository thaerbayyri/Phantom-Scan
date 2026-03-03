import { useState, useCallback, useRef, type ReactNode } from "react";

interface ResizableWrapperProps {
    children: ReactNode;
    defaultHeight: number;
    minHeight?: number;
    maxHeight?: number;
    className?: string;
}

/**
 * Wraps any component with a bottom drag-handle for vertical resizing.
 * Uses React state (not CSS resize) so it works with Plotly/Canvas children.
 */
export function ResizableWrapper({
    children,
    defaultHeight,
    minHeight = 80,
    maxHeight = 800,
    className = "",
}: ResizableWrapperProps) {
    const [height, setHeight] = useState(defaultHeight);
    const containerRef = useRef<HTMLDivElement>(null);
    const dragging = useRef(false);
    const startY = useRef(0);
    const startH = useRef(0);

    const onPointerDown = useCallback(
        (e: React.PointerEvent) => {
            e.preventDefault();
            dragging.current = true;
            startY.current = e.clientY;
            startH.current = height;
            (e.target as HTMLElement).setPointerCapture(e.pointerId);
        },
        [height],
    );

    const onPointerMove = useCallback(
        (e: React.PointerEvent) => {
            if (!dragging.current) return;
            const delta = e.clientY - startY.current;
            setHeight(Math.max(minHeight, Math.min(maxHeight, startH.current + delta)));
        },
        [minHeight, maxHeight],
    );

    const onPointerUp = useCallback(() => {
        dragging.current = false;
    }, []);

    return (
        <div
            ref={containerRef}
            className={`relative ${className}`}
            style={{ height: `${height}px` }}
        >
            {children}
            {/* Drag handle */}
            <div
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                className="absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize flex items-center justify-center group z-10"
            >
                <div className="w-10 h-1 rounded-full bg-muted-foreground/20 group-hover:bg-primary/50 transition-colors" />
            </div>
        </div>
    );
}
