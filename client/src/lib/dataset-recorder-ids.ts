/**
 * Start gate for the Training Data Capture panel. The fields start EMPTY on purpose: a default such as
 * "room1" / "s1" silently puts a new recording into an old training folder under the wrong subject.
 * This only decides whether the existing client Start action is enabled; nothing is sent to a node (F2).
 */
export const INITIAL_ROOM_ID = "";
export const INITIAL_SUBJECT_ID = "";

/** Room ID becomes a folder name under data/datasets/: lowercase letters, digits and hyphens only. */
export const ROOM_ID_PATTERN = /^[a-z0-9-]+$/;

export function canStartDatasetRecording(roomId: string, subjectId: string): boolean {
  return ROOM_ID_PATTERN.test(roomId) && subjectId.length > 0;
}
